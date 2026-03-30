/**
 * Voice Live WebSocket クライアント。
 * Azure Voice Live API に接続し、リアルタイム音声対話を行う。
 */

export interface VoiceLiveConfig {
  endpoint: string
  token: string
  agentName: string
  projectName: string
  apiVersion: string
}

export interface VoiceLiveHandlers {
  onTranscript: (text: string, isFinal: boolean) => void
  onAgentText: (text: string) => void
  onError: (error: string) => void
  onStateChange: (state: 'connecting' | 'connected' | 'listening' | 'processing' | 'speaking' | 'disconnected') => void
}

export class VoiceLiveClient {
  private ws: WebSocket | null = null
  private mediaStream: MediaStream | null = null
  private audioContext: AudioContext | null = null
  private sourceNode: MediaStreamAudioSourceNode | null = null
  private processorNode: ScriptProcessorNode | null = null
  private playbackContext: AudioContext | null = null
  private handlers: VoiceLiveHandlers
  private config: VoiceLiveConfig

  constructor(config: VoiceLiveConfig, handlers: VoiceLiveHandlers) {
    this.config = config
    this.handlers = handlers
  }

  async connect(): Promise<void> {
    this.handlers.onStateChange('connecting')

    // Voice Live API: agent_id と project_id を使用（agent_name/project_name ではない）
    const url = `${this.config.endpoint}?api-version=${this.config.apiVersion}`
      + `&agent_id=${encodeURIComponent(this.config.agentName)}`
      + `&project_id=${encodeURIComponent(this.config.projectName)}`

    return new Promise<void>((resolve, reject) => {
      // api-key クエリパラメータで認証（WSS で暗号化済み）
      const authUrl = `${url}&api-key=${encodeURIComponent(this.config.token)}`
      this.ws = new WebSocket(authUrl)

      this.ws.onopen = () => {
        this.handlers.onStateChange('connected')
        this.sendSessionUpdate()
        this.startMicrophone()
        resolve()
      }

      this.ws.onmessage = (event: MessageEvent) => {
        if (typeof event.data !== 'string') return
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>
          this.handleServerEvent(data)
        } catch {
          // バイナリ音声データの場合は無視
        }
      }

      this.ws.onerror = () => {
        this.handlers.onError('Voice Live 接続エラー')
        this.handlers.onStateChange('disconnected')
        reject(new Error('Voice Live WebSocket connection failed'))
      }

      this.ws.onclose = () => {
        this.handlers.onStateChange('disconnected')
        this.cleanup()
      }
    })
  }

  private sendSessionUpdate(): void {
    if (!this.ws) return
    this.ws.send(JSON.stringify({
      type: 'session.update',
      session: {
        modalities: ['text', 'audio'],
        voice: {
          name: 'ja-JP-NanamiNeural',
          type: 'azure-standard',
        },
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        input_audio_sampling_rate: 24000,
        input_audio_transcription: {
          model: 'azure-speech',
        },
        turn_detection: {
          type: 'azure_semantic_vad',
          silence_duration_ms: 500,
        },
        input_audio_noise_reduction: { type: 'azure_deep_noise_suppression' },
        input_audio_echo_cancellation: { type: 'server_echo_cancellation' },
      },
    }))
  }

  private async startMicrophone(): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 24000, channelCount: 1, echoCancellation: true },
      })

      this.audioContext = new AudioContext({ sampleRate: 24000 })
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream)
      this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1)

      this.processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
        if (this.ws?.readyState !== WebSocket.OPEN) return
        const inputData = e.inputBuffer.getChannelData(0)
        // Float32 → Int16 PCM 変換
        const pcm16 = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
        }
        const bytes = new Uint8Array(pcm16.buffer)
        let binary = ''
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i])
        }
        const base64 = btoa(binary)
        this.ws.send(JSON.stringify({
          type: 'input_audio_buffer.append',
          audio: base64,
        }))
      }

      // サイレント gain ノードでフィードバック防止
      const silentGain = this.audioContext.createGain()
      silentGain.gain.value = 0
      this.sourceNode.connect(this.processorNode)
      this.processorNode.connect(silentGain)
      silentGain.connect(this.audioContext.destination)
      this.handlers.onStateChange('listening')
    } catch {
      this.handlers.onError('マイクの使用が許可されていません')
      this.handlers.onStateChange('disconnected')
    }
  }

  private handleServerEvent(event: Record<string, unknown>): void {
    const type = event.type as string

    switch (type) {
      case 'session.created':
      case 'session.updated':
        break

      case 'input_audio_buffer.speech_started':
        this.handlers.onStateChange('listening')
        break

      case 'input_audio_buffer.speech_stopped':
        this.handlers.onStateChange('processing')
        break

      case 'conversation.item.input_audio_transcription.completed': {
        const transcript = (event as { transcript?: string }).transcript || ''
        if (transcript) {
          this.handlers.onTranscript(transcript, true)
        }
        break
      }

      case 'conversation.item.input_audio_transcription.delta': {
        const delta = (event as { delta?: string }).delta || ''
        if (delta) {
          this.handlers.onTranscript(delta, false)
        }
        break
      }

      case 'response.audio.delta': {
        const audioData = (event as { delta?: string }).delta
        if (audioData) {
          this.playAudio(audioData)
          this.handlers.onStateChange('speaking')
        }
        break
      }

      case 'response.audio_transcript.delta': {
        const text = (event as { delta?: string }).delta || ''
        if (text) {
          this.handlers.onAgentText(text)
        }
        break
      }

      case 'response.done':
        this.handlers.onStateChange('listening')
        break

      case 'error': {
        const msg = (event as { error?: { message?: string } }).error?.message || 'Unknown error'
        this.handlers.onError(msg)
        break
      }
    }
  }

  private async playAudio(base64Audio: string): Promise<void> {
    try {
      if (!this.playbackContext) {
        this.playbackContext = new AudioContext({ sampleRate: 24000 })
      }
      const binaryString = atob(base64Audio)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }
      // Int16 PCM → Float32 変換
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x8000
      }
      const buffer = this.playbackContext.createBuffer(1, float32.length, 24000)
      buffer.getChannelData(0).set(float32)
      const source = this.playbackContext.createBufferSource()
      source.buffer = buffer
      source.connect(this.playbackContext.destination)
      source.start()
    } catch {
      // 音声再生エラー — サイレントに処理
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.cleanup()
  }

  private cleanup(): void {
    this.processorNode?.disconnect()
    this.sourceNode?.disconnect()
    void this.audioContext?.close()
    this.mediaStream?.getTracks().forEach(t => t.stop())
    void this.playbackContext?.close()
    this.processorNode = null
    this.sourceNode = null
    this.audioContext = null
    this.mediaStream = null
    this.playbackContext = null
  }
}
