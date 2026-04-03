// Azure Logic Apps (Consumption)
// post_approval_actions 用の HTTP workflow。
// Teams を使う manager approval workflow は別途用意し、MANAGER_APPROVAL_TRIGGER_URL で FastAPI に渡す。

param name string
param location string
param tags object = {}

resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        manual: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            schema: {
              type: 'object'
              properties: {
                request_type: { type: 'string' }
                plan_title: { type: 'string' }
                plan_markdown: { type: 'string' }
                brochure_html: { type: 'string' }
                conversation_id: { type: 'string' }
              }
              required: [
                'request_type'
                'conversation_id'
              ]
            }
          }
        }
      }
      actions: {
        Response: {
          type: 'Response'
          kind: 'Http'
          inputs: {
            statusCode: 202
            body: {
              status: 'accepted'
              message: 'Logic Apps workflow accepted the request'
            }
          }
        }
      }
    }
  }
}

output id string = logicApp.id
output name string = logicApp.name
@secure()
output callbackUrl string = logicApp.listCallbackUrl().value
output principalId string = logicApp.identity.principalId
