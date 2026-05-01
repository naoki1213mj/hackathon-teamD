"""ontology_v2_decoded.json から構造サマリを生成する補助スクリプト。"""
import json
from pathlib import Path

src = Path(__file__).parent / "ontology_v2_decoded.json"
d = json.load(open(src, encoding="utf-8"))

entities: dict = {}
bindings: dict = {}
rels: dict = {}
ctxs: dict = {}
for p in d:
    path = p.get("path") or ""
    payload = p.get("payload", {})
    if not isinstance(payload, dict):
        continue
    if "EntityTypes/" in path and path.endswith("/definition.json"):
        entities[payload.get("id")] = payload
    elif "EntityTypes/" in path and "DataBindings/" in path:
        eid = path.split("/")[1]
        bindings[eid] = payload
    elif "RelationshipTypes/" in path and path.endswith("/definition.json"):
        rels[payload.get("id")] = payload
    elif "RelationshipTypes/" in path and "Contextualizations/" in path:
        rid = path.split("/")[1]
        ctxs[rid] = payload

print(f"entities={len(entities)} bindings={len(bindings)} rels={len(rels)} ctxs={len(ctxs)}")
for eid, e in entities.items():
    name = e.get("name")
    props = e.get("properties") or []
    ts = e.get("timeseriesProperties") or []
    print()
    print(f"[{eid}] {name}: properties={len(props)}, timeseries={len(ts)}, displayNamePropertyId={e.get('displayNamePropertyId')}, entityIdParts={e.get('entityIdParts')}")
    for prop in props:
        print(f"  prop  {prop['name']:30s} {prop['valueType']}")
    for prop in ts:
        print(f"  TS    {prop['name']:30s} {prop['valueType']}")
print()
print("--- relationships ---")
for rid, r in rels.items():
    print(f"  {rid} {r.get('name')} src={r.get('source', {}).get('entityTypeId')} tgt={r.get('target', {}).get('entityTypeId')}")

print()
print("--- bindings (table -> sourceTable) ---")
for eid, b in bindings.items():
    cfg = b.get("dataBindingConfiguration") or {}
    sp = cfg.get("sourceTableProperties") or {}
    print(f"  entity={eid} type={cfg.get('dataBindingType')} table={sp.get('sourceSchema')}.{sp.get('sourceTableName')} timestamp={cfg.get('timestampColumnName')}")

print()
print("--- contextualizations (relationship -> binding table) ---")
for rid, c in ctxs.items():
    bt = c.get("dataBindingTable") or {}
    src_b = c.get("sourceKeyRefBindings") or []
    tgt_b = c.get("targetKeyRefBindings") or []
    src_cols = ",".join(b.get("sourceColumnName") for b in src_b)
    tgt_cols = ",".join(b.get("sourceColumnName") for b in tgt_b)
    print(f"  rel={rid} table={bt.get('sourceSchema')}.{bt.get('sourceTableName')} srcKey={src_cols} fk={tgt_cols}")
