"""Explicit registered-source replay and local version registration; no fake fetches."""
from __future__ import annotations
import copy
import difflib
import hashlib
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse
from case_store import digest, utcnow
from dataset_runtime import load_runtime, DEFAULT_ROOT

ESG_SOURCE='SRC-ESG-EBA-GL-2025-01'

def open_registered_case(store,goal,mode,root=DEFAULT_ROOT,nonce=None):
    root=Path(root)
    files=load_runtime(root)
    manifest=json.loads((root/'dataset_manifest.json').read_text())
    change=next(c for c in files['regulatory_sources/change_register.json']['changes'] if c['topic_key']=='esg_risk_management')
    key=digest(dict(source_id=ESG_SOURCE,change=change,inputs=files,goal=goal,mode=mode,nonce=nonce))
    case_id,created=store.create_case(goal,files,manifest['dataset_version'],manifest['scenario_as_of_date'],mode,key)
    if created:
        store.put(case_id,'SourceVersion','registered-event',dict(source_id=ESG_SOURCE,change=change,
            intake_mode='registered_source_replay',observed_at=utcnow(),content_sha256=None,
            note='Replays the registered candidate. No current network monitoring or complete amendment audit was performed.'),
            ['file:regulatory_sources/change_register.json'],'recorded')
    return case_id,created


def register_local_snapshot(store,case_id,version,artifact,artifact_root):
    """Local CLI/service only. A user-supplied file is an unverified official candidate."""
    inputs=store.inputs(case_id)
    pair=inputs['regulatory_sources/version_pairs.json'][0]
    metadata=next((pair[k] for k in ('older','newer') if pair[k]['identifier']==version),None)
    if not metadata or urlparse(metadata['url']).hostname!='www.eba.europa.eu':
        raise ValueError('Version is not in the selected official ESG source registry')
    artifact=Path(artifact)
    if not artifact.is_file() or artifact.suffix.lower() not in ('.pdf','.txt'):
        raise ValueError('Provide an existing .pdf or .txt source candidate')
    if not 0<artifact.stat().st_size<=30_000_000:raise ValueError('Source file must be nonempty and at most 30 MB')
    raw=artifact.read_bytes()
    if artifact.suffix.lower()=='.pdf' and not raw.startswith(b'%PDF-'):raise ValueError('Not a PDF file')
    if artifact.suffix.lower()=='.txt':raw.decode('utf-8')
    sha=hashlib.sha256(raw).hexdigest();base=Path(artifact_root).resolve();base.mkdir(parents=True,exist_ok=True)
    target=base/(sha+artifact.suffix.lower())
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Stored source artefact was modified')
    if not target.exists():shutil.copyfile(artifact,target)
    key=version+':'+sha
    prior=store.get(case_id,'SourceVersion',key)
    if prior:return prior
    return store.put(case_id,'SourceVersion',key,dict(metadata,source_id=ESG_SOURCE,
        local_artifact=target.name,content_sha256=sha,acquisition='user_supplied_unverified',
        authenticity_status='needs_review',registered_at=utcnow()),['source:'+ESG_SOURCE],'recorded')


def _text(record,artifact_root):
    root=Path(artifact_root).resolve();path=(root/record['local_artifact']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('Missing or invalid source path')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=record['content_sha256']:raise ValueError('Source hash mismatch')
    if path.suffix=='.pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('PDF extraction needs pypdf; retain original file and install dependency before extraction')
        return '\n'.join(f'[Page {i+1}]\n{p.extract_text() or ""}' for i,p in enumerate(PdfReader(path).pages))
    return data.decode('utf-8')


def compare_versions(store,case_id,artifact_root):
    pair=copy.deepcopy(store.inputs(case_id)['regulatory_sources/version_pairs.json'][0])
    rows=[o['payload'] for o in store.objects(case_id,'SourceVersion') if o['payload'].get('local_artifact')]
    selected=[]
    for side in ('older','newer'):
        candidates=[r for r in rows if r['identifier']==pair[side]['identifier']]
        if len(candidates)>1:return dict(status='ambiguous_versions',reason='Select/review conflicting source hashes before comparison')
        if not candidates:return dict(status='insufficient_source_snapshots',missing_identifier=pair[side]['identifier'],comparison_kind=pair['comparison_kind'])
        selected.append(candidates[0])
    texts=[_text(r,artifact_root) for r in selected]
    if any(not t.strip() for t in texts):return dict(status='insufficient_extracted_text')
    diff='\n'.join(difflib.unified_diff(texts[0].splitlines(),texts[1].splitlines(),fromfile=selected[0]['identifier'],tofile=selected[1]['identifier'],lineterm=''))
    return dict(status='candidate_text_diff',comparison_kind=pair['comparison_kind'],
        diff=diff[:18000],truncated=len(diff)>18000,content_sha256=[r['content_sha256'] for r in selected],
        authenticity_status='needs_review',note='Text comparison of supplied files; consultation is not prior binding law. No authenticity or legal-materiality approval.')


def read_snapshot(store,case_id,identifier,artifact_root,offset=0,limit=6000):
    rows=[o['payload'] for o in store.objects(case_id,'SourceVersion') if o['payload'].get('identifier')==identifier and o['payload'].get('local_artifact')]
    if len(rows)!=1:return dict(status='insufficient_source_snapshots' if not rows else 'ambiguous_versions',identifier=identifier)
    text=_text(rows[0],artifact_root)
    return dict(status='ok',identifier=identifier,text=text[offset:offset+limit],offset=offset,
                has_more=offset+limit<len(text),text_kind='supplied_source_text',authenticity_status='needs_review',
                content_sha256=rows[0]['content_sha256'],official_url=rows[0]['url'])
