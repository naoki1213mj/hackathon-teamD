"""verify_foundry_fabric_connection の shape classifier の単体テスト。

rubber-duck `verify-script-fix-rubber-duck` blocking #2 反映:
metadata.type による Fabric Data Agent 識別が `fabric_workspace` 等の他 Fabric
connection を false-green しないことを保証する。
"""

from __future__ import annotations

from scripts.verify_foundry_fabric_connection import (
    _classify_fabric_da_shape,
    _extract_metadata_type,
)


class _MetadataWithType:
    """object 形式の metadata (dict 以外) を simulate するヘルパー。"""

    def __init__(self, type_value: str) -> None:
        self.type = type_value


def test_classify_metadata_fabric_dataagent_preview_is_accepted() -> None:
    """ポータル作成直後のリアル shape (実機 2026-05-03 確認) は accept される。"""
    kind, detail = _classify_fabric_da_shape(
        metadata_type="fabric_dataagent_preview",
        category="ConnectionType.CUSTOM",
        target="-",
    )
    assert kind == "metadata"
    assert "fabric_dataagent_preview" in detail


def test_classify_metadata_fabric_dataagent_v2_forward_compat() -> None:
    """将来の variant `fabric_dataagent_v2` 等も prefix で accept される。"""
    kind, _ = _classify_fabric_da_shape(
        metadata_type="fabric_dataagent_v2",
        category="ConnectionType.CUSTOM",
        target="-",
    )
    assert kind == "metadata"


def test_classify_metadata_fabric_workspace_is_rejected() -> None:
    """rubber-duck blocking #1: 非 DA Fabric connection (workspace) は reject。"""
    kind, detail = _classify_fabric_da_shape(
        metadata_type="fabric_workspace",
        category="ConnectionType.CUSTOM",
        target="-",
    )
    assert kind == "none"
    assert "未検出" in detail


def test_classify_metadata_fabric_lakehouse_is_rejected() -> None:
    """rubber-duck blocking #1: 非 DA Fabric connection (lakehouse) は reject。"""
    kind, _ = _classify_fabric_da_shape(
        metadata_type="fabric_lakehouse",
        category="ConnectionType.CUSTOM",
        target="-",
    )
    assert kind == "none"


def test_classify_legacy_category_fabric_data_agent() -> None:
    """legacy SDK shape: category=`FabricDataAgent` も accept される。"""
    kind, detail = _classify_fabric_da_shape(
        metadata_type="",
        category="FabricDataAgent",
        target="https://example/dataagents/abc",
    )
    # metadata 不在のため category match に降格、それでも accept
    assert kind == "category"
    assert "FabricDataAgent" in detail


def test_classify_legacy_category_with_whitespace() -> None:
    """category に余計な空白が混じっても normalization で吸収される。"""
    kind, _ = _classify_fabric_da_shape(
        metadata_type="",
        category="Fabric Data Agent",
        target="-",
    )
    assert kind == "category"


def test_classify_legacy_category_generic_fabric_is_rejected() -> None:
    """rubber-duck blocking #1: category=`FabricWorkspace` は reject される。"""
    kind, _ = _classify_fabric_da_shape(
        metadata_type="",
        category="FabricWorkspace",
        target="-",
    )
    assert kind == "none"


def test_classify_target_dataagents_path_accepts() -> None:
    """legacy URL shape: target に `/dataagents/` を含めば accept。"""
    kind, detail = _classify_fabric_da_shape(
        metadata_type="",
        category="CustomKeys",
        target="https://api.fabric.microsoft.com/v1/workspaces/abc/dataagents/xyz/aiassistant/openai",
    )
    assert kind == "target"
    assert "legacy" in detail


def test_classify_no_signal_returns_none() -> None:
    """全 signal 不在は none → fail-closed で commands 非表示になる。"""
    kind, detail = _classify_fabric_da_shape(
        metadata_type="",
        category="CustomKeys",
        target="-",
    )
    assert kind == "none"
    assert "未検出" in detail
    assert "metadata.type=`-`" in detail


def test_classify_case_insensitive_metadata() -> None:
    """metadata.type は大文字でも小文字 normalize される。"""
    kind, _ = _classify_fabric_da_shape(
        metadata_type="FABRIC_DATAAGENT_PREVIEW",
        category="-",
        target="-",
    )
    assert kind == "metadata"


def test_extract_metadata_type_from_dict() -> None:
    assert _extract_metadata_type({"type": "fabric_dataagent_preview"}) == "fabric_dataagent_preview"
    assert _extract_metadata_type({"type": "FABRIC_DATAAGENT_PREVIEW"}) == "fabric_dataagent_preview"
    assert _extract_metadata_type({}) == ""


def test_extract_metadata_type_from_object() -> None:
    """SDK が dict ではなく object 形式で metadata を露出するケース。"""
    obj = _MetadataWithType("fabric_dataagent_preview")
    assert _extract_metadata_type(obj) == "fabric_dataagent_preview"


def test_extract_metadata_type_handles_none() -> None:
    assert _extract_metadata_type(None) == ""
