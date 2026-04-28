"""Static IaC checks for private Container Apps to Cosmos connectivity."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_container_apps_environment_uses_dedicated_vnet_subnet() -> None:
    main = _read("infra/main.bicep")
    vnet = _read("infra/modules/vnet.bicep")
    env = _read("infra/modules/container-apps-env.bicep")
    parameters = _read("infra/main.parameters.json")

    assert "param enableContainerAppsVnetIntegration bool = false" in main
    assert "param containerAppsVnetIntegrationMigrationApproval string = ''" in main
    assert (
        "var containerAppsVnetIntegrationApproved = enableContainerAppsVnetIntegration "
        "&& containerAppsVnetIntegrationMigrationApproval == 'CONFIRM_CAE_VNET_MIGRATION'"
    ) in main
    assert "subnetId: containerAppsVnetIntegrationApproved ? vnet.outputs.containerAppsSubnetId : ''" in main
    assert "ENABLE_CONTAINER_APPS_VNET_INTEGRATION=false" in parameters
    assert "CONTAINER_APPS_VNET_INTEGRATION_MIGRATION_APPROVAL=" in parameters
    assert "name: 'snet-container-apps'" in vnet
    assert "serviceName: 'Microsoft.App/environments'" in vnet
    assert "infrastructureSubnetId: subnetId" in env


def test_cosmos_private_endpoint_dns_and_public_network_are_locked_down() -> None:
    main = _read("infra/main.bicep")
    cosmos = _read("infra/modules/cosmos-db.bicep")

    cosmos_module_start = main.index("module cosmosDb 'modules/cosmos-db.bicep'")
    cosmos_module_end = main.index("module cosmosDbAccess 'modules/cosmos-db-access.bicep'")
    cosmos_module = main[cosmos_module_start:cosmos_module_end]

    assert "privateEndpointsSubnetId: containerAppsVnetIntegrationApproved ? vnet.outputs.privateEndpointsSubnetId : ''" in cosmos_module
    assert "publicNetworkAccess: !empty(privateEndpointsSubnetId) ? 'Disabled' : 'Enabled'" in cosmos
    assert "name: 'privatelink.documents.azure.com'" in cosmos
    assert "Microsoft.Network/privateDnsZones/virtualNetworkLinks" in cosmos
    assert "Microsoft.Network/privateEndpoints/privateDnsZoneGroups" in cosmos
    assert "privateDnsZoneId: privateDnsZone.id" in cosmos


def test_container_app_scale_out_stays_approval_controlled_until_private_path_verified() -> None:
    main = _read("infra/main.bicep")
    container_app = _read("infra/modules/container-app.bicep")
    parameters = _read("infra/main.parameters.json")

    assert "param containerAppMaxReplicas int = 1" in main
    assert "maxReplicas: containerAppMaxReplicas" in main
    assert "CONTAINER_APP_MAX_REPLICAS=1" in parameters
    assert "param maxReplicas int = 1" in container_app
    assert "maxReplicas: maxReplicas" in container_app


def test_deploy_workflow_uses_ci_head_sha_for_workflow_run_deployments() -> None:
    """workflow_run deploy は CI 済み commit SHA を checkout / image tag に使う。"""
    deploy = _read(".github/workflows/deploy.yml")

    assert "DEPLOY_SHA: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}" in deploy
    assert "ref: ${{ env.DEPLOY_SHA }}" in deploy
    assert "--image travel-agents:${DEPLOY_SHA}" in deploy
    assert "--image ${{ vars.ACR_NAME }}.azurecr.io/travel-agents:${DEPLOY_SHA}" in deploy


def test_mai_parameters_are_wired_to_azd_parameter_file() -> None:
    """MAI endpoint/RBAC parameters documented for azd are passed into Bicep."""
    parameters = _read("infra/main.parameters.json")

    assert "IMAGE_PROJECT_ENDPOINT_MAI=" in parameters
    assert "MAI_RESOURCE_NAME=" in parameters


def test_bicep_provisions_runtime_default_gpt_image_model() -> None:
    """Fresh environments provision the image deployment selected by the app default."""
    main = _read("infra/main.bicep")
    ai_services = _read("infra/modules/ai-services.bicep")

    assert "var defaultImageModelDeploymentName = 'gpt-image-2'" in main
    assert "param imageModelDeploymentName string = 'gpt-image-2'" in ai_services
    assert "name: 'gpt-image-2'" in ai_services
    assert "version: '2026-04-21'" in ai_services
