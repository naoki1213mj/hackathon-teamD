// Azure Logic Apps (Consumption)
// 上司承認リンクを Teams DM で送る通知専用 workflow。
// 既存の post_approval_actions Logic App とは分離し、既存の Microsoft.Web/connections/teams を再利用する。

param name string
param location string
param teamsConnectionId string
param teamsManagedApiId string
param teamsConnectionName string = 'teams'
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
      parameters: {
        '$connections': {
          type: 'Object'
          defaultValue: {}
        }
      }
      triggers: {
        manual: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            schema: {
              type: 'object'
              properties: {
                request_type: {
                  type: 'string'
                }
                plan_title: {
                  type: 'string'
                }
                plan_markdown: {
                  type: 'string'
                }
                conversation_id: {
                  type: 'string'
                }
                manager_email: {
                  type: 'string'
                }
                manager_approval_url: {
                  type: 'string'
                }
                manager_callback_url: {
                  type: 'string'
                }
                manager_callback_token: {
                  type: 'string'
                }
              }
              required: [
                'request_type'
                'plan_title'
                'conversation_id'
                'manager_email'
                'manager_approval_url'
              ]
            }
          }
        }
      }
      actions: {
        Compose_manager_message: {
          type: 'Compose'
          inputs: '''@concat('上司承認依頼: ', triggerBody()?['plan_title'], decodeUriComponent('%0A%0A'), '承認ページ: ', triggerBody()?['manager_approval_url'], decodeUriComponent('%0A%0A'), 'Conversation ID: ', triggerBody()?['conversation_id'])'''
          runAfter: {}
        }
        Send_manager_message: {
          type: 'ApiConnection'
          runAfter: {
            Compose_manager_message: [
              'Succeeded'
            ]
          }
          inputs: {
            host: {
              connection: {
                name: '''@parameters('$connections')['teams']['connectionId']'''
              }
            }
            method: 'post'
            path: '/flowbot/actions/notification/recipienttypes/user'
            body: {
              messageBody: '''@{outputs('Compose_manager_message')}'''
              recipient: {
                to: '''@{triggerBody()?['manager_email']}'''
                summary: '''@{triggerBody()?['plan_title']}'''
                isAlert: true
              }
            }
          }
        }
        Response_succeeded: {
          type: 'Response'
          kind: 'Http'
          runAfter: {
            Send_manager_message: [
              'Succeeded'
            ]
          }
          inputs: {
            statusCode: 202
            body: {
              status: 'accepted'
              conversation_id: '''@{triggerBody()?['conversation_id']}'''
              target: '''@{triggerBody()?['manager_email']}'''
            }
          }
        }
        Response_failed_send_message: {
          type: 'Response'
          kind: 'Http'
          runAfter: {
            Send_manager_message: [
              'Failed'
              'TimedOut'
            ]
          }
          inputs: {
            statusCode: 502
            body: {
              status: 'failed'
              message: 'Teams manager approval notification failed'
              conversation_id: '''@{triggerBody()?['conversation_id']}'''
            }
          }
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          teams: {
            connectionId: teamsConnectionId
            connectionName: teamsConnectionName
            id: teamsManagedApiId
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
