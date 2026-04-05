"""Merge specialist agent results into final output files for analyse-transcript pipeline."""
import json, glob, re, os, sys
from collections import Counter
from datetime import datetime, timezone

FN = sys.argv[1] if len(sys.argv) > 1 else 'UCs5CHx-kIwy2NF9DFesWE8w_8Kc3P1BQEUE'
ROUND = int(sys.argv[2]) if len(sys.argv) > 2 else 3
BASE = 'data/transcripts/analysed'

# 1. Merge all chapter results
all_sub_topics, all_claims, all_corrections = [], [], []
per_chapter = {}

for path in sorted(glob.glob(f'{BASE}/{FN}.ch*.results.json')):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    ch_id = data['chapter_id']
    st = data.get('sub_topics', [])
    cl = data.get('claims', [])
    co = data.get('corrections', [])
    all_sub_topics.extend(st)
    all_claims.extend(cl)
    all_corrections.extend(co)
    per_chapter[f'ch{ch_id}'] = {'sub_topics': len(st), 'corrections': len(co), 'claims': len(cl)}
    print(f'Ch{ch_id}: {len(st)} st, {len(co)} corr, {len(cl)} claims')

print(f'\nRaw: {len(all_sub_topics)} st, {len(all_claims)} claims, {len(all_corrections)} corr')

# 2. Normalize claim types
valid_types = {'buy', 'sell', 'hold', 'captain', 'avoid', 'breakout', 'matchup_edge'}
type_map = {
    'buy_recommendation': 'buy', 'must_buy': 'buy', 'conditional_buy': 'buy',
    'speculative_buy': 'buy', 'sell_recommendation': 'sell', 'sell_consideration': 'sell',
    'hold_recommendation': 'hold', 'avoid_recommendation': 'avoid', 'do_not_buy': 'avoid',
    'not_a_target': 'avoid', 'captaincy': 'captain', 'watchlist': 'hold',
    'price_watch': 'hold', 'return_watch': 'hold', 'pod_option': 'buy',
    'role_concern': 'hold', 'role_change': 'hold', 'role_confirmation': 'hold',
    'minutes_risk': 'hold', 'start_recommendation': 'buy',
}
drop_types = {'mention', 'positive_mention', 'performance_note', 'injury', 'try_scoring_record'}

normalized = []
dropped = []
for c in all_claims:
    ct = c.get('claim_type', '')
    if ct in valid_types:
        normalized.append(c)
    elif ct in type_map:
        c['claim_type'] = type_map[ct]
        normalized.append(c)
    elif ct in drop_types:
        dropped.append((c.get('player_name'), ct))
    else:
        dropped.append((c.get('player_name'), ct))

print(f'Normalized: {len(normalized)} ({len(dropped)} dropped)')
if dropped:
    print(f'Dropped: {dropped}')

# 3. Deduplicate cross-chapter
sorted_claims = sorted(normalized, key=lambda x: x.get('start_ts', 0))
seen = {}
deduped = []
for c in sorted_claims:
    key = (c.get('player_name'), c.get('claim_type'))
    ch = c.get('chapter_id')
    tl = len(c.get('claim_text', ''))
    if key in seen:
        pi, pc, pl = seen[key]
        if ch != pc:
            if tl > pl:
                c['also_discussed_in'] = [pc]
                deduped[pi] = None
                seen[key] = (len(deduped), ch, tl)
                deduped.append(c)
            else:
                if deduped[pi]:
                    deduped[pi].setdefault('also_discussed_in', []).append(ch)
        else:
            deduped.append(c)
    else:
        seen[key] = (len(deduped), ch, tl)
        deduped.append(c)

final = [c for c in deduped if c is not None]
for i, c in enumerate(final):
    sid = c.get('sub_topic_id', 'unknown')
    c['claim_id'] = f'{sid}_c{i+1}'

print(f'Deduped: {len(final)} claims')
ct = Counter(c['claim_type'] for c in final)
print(f'Types: {dict(sorted(ct.items()))}')

# 4. Apply name corrections
with open(f'data/transcripts/clean/{FN}.json', 'r', encoding='utf-8') as f:
    transcript = json.load(f)
segments = transcript['segments']
applied = failed = 0
for corr in all_corrections:
    idx = corr.get('segment_idx')
    orig = corr.get('original', '')
    fix = corr.get('corrected', '')
    if idx is None or idx >= len(segments):
        failed += 1
        continue
    txt = segments[idx]['text']
    if orig in txt:
        segments[idx]['text'] = txt.replace(orig, fix, 1)
        applied += 1
    else:
        pat = re.compile(re.escape(orig), re.IGNORECASE)
        if pat.search(txt):
            segments[idx]['text'] = pat.sub(fix, txt, count=1)
            applied += 1
        else:
            failed += 1

print(f'Corrections: {applied}/{len(all_corrections)} applied')

# 5. Write claims.json
with open(f'{BASE}/{FN}.claims.json', 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)

# 6. Write clean.json
with open(f'{BASE}/{FN}.clean.json', 'w', encoding='utf-8') as f:
    json.dump(transcript, f, indent=2, ensure_ascii=False)

# 7. Write topics.json
with open(f'{BASE}/{FN}.chapters.json', 'r', encoding='utf-8') as f:
    chapters = json.load(f)['chapters']

st_by_ch = {}
for st in all_sub_topics:
    cid = int(st.get('sub_topic_id', 'ch0_st0').split('_')[0].replace('ch', ''))
    st_by_ch.setdefault(cid, []).append(st)

claims_by_st = {}
for c in final:
    claims_by_st.setdefault(c.get('sub_topic_id', ''), []).append(c.get('claim_id', ''))

topics = {
    'video_id': transcript.get('video_id', FN.split('_')[-1]),
    'title': transcript.get('title', ''),
    'round': ROUND,
    'total_segments': len(segments),
    'chapters': []
}
for ch in chapters:
    ce = {
        'chapter_id': ch['chapter_id'], 'type': ch['type'], 'title': ch['title'],
        'start_ts': ch['start_ts'], 'end_ts': ch['end_ts'],
        'start_seg_idx': ch['start_seg_idx'], 'end_seg_idx': ch['end_seg_idx'],
        'segment_count': ch['end_seg_idx'] - ch['start_seg_idx'] + 1,
        'teams': ch.get('teams', []), 'context_hint': ch.get('context_hint', ''),
        'sub_topics': []
    }
    for st in st_by_ch.get(ch['chapter_id'], []):
        se = dict(st)
        se['claim_ids'] = claims_by_st.get(st.get('sub_topic_id', ''), [])
        ce['sub_topics'].append(se)
    topics['chapters'].append(ce)

with open(f'{BASE}/{FN}.topics.json', 'w', encoding='utf-8') as f:
    json.dump(topics, f, indent=2, ensure_ascii=False)

# 8. Write analysed.json
analysed = dict(transcript)
analysed['round'] = ROUND
analysed['chapters'] = []
for ch in chapters:
    ce = {
        'chapter_id': ch['chapter_id'], 'type': ch['type'], 'title': ch['title'],
        'start_ts': ch['start_ts'], 'end_ts': ch['end_ts'],
        'teams': ch.get('teams', []), 'sub_topics': []
    }
    for st in st_by_ch.get(ch['chapter_id'], []):
        ce['sub_topics'].append({
            'sub_topic_id': st.get('sub_topic_id', ''),
            'title': st.get('title', ''),
            'start_ts': st.get('start_ts', 0),
            'end_ts': st.get('end_ts', 0),
            'players': st.get('players', []),
            'teams': st.get('teams', []),
            'summary': st.get('summary', '')
        })
    analysed['chapters'].append(ce)

with open(f'{BASE}/{FN}.json', 'w', encoding='utf-8') as f:
    json.dump(analysed, f, indent=2, ensure_ascii=False)

# 9. Write manifest
manifest = {
    'pipeline_version': 'analyse-v1',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'input': {'raw_path': f'data/transcripts/raw/{FN}.json', 'clean_path': f'data/transcripts/clean/{FN}.json'},
    'round_context': {
        'round': ROUND,
        'teams_playing': ['Broncos', 'Bulldogs', 'Cowboys', 'Dolphins', 'Dragons', 'Eels', 'Knights', 'Panthers', 'Rabbitohs', 'Raiders', 'Roosters', 'Sharks', 'Storm', 'Tigers', 'Titans', 'Warriors'],
        'byes': [], 'confidence': 'round'
    },
    'phase1': {'deterministic_corrections': 213, 'phonetic_corrections': 287, 'flagged': 283, 'keyword_blocks': 18},
    'phase2': {'model': 'sonnet', 'chapters_detected': len(chapters), 'chapter_types': dict(Counter(ch['type'] for ch in chapters))},
    'chapters': chapters,
    'phase3': {
        'model': 'opus', 'agents_spawned': 12,
        'sub_topics_total': len(all_sub_topics),
        'claims_raw': len(all_claims),
        'claims_after_normalize': len(normalized),
        'claims_after_dedup': len(final),
        'name_corrections': len(all_corrections),
        'name_corrections_applied': applied,
        'skipped_chapters': [1],
        'per_chapter': per_chapter
    },
    'phase4': {'verification_skipped': True, 'reason': 'Haiku verification deferred', 'claims_final': len(final)}
}

with open(f'{BASE}/{FN}.manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

# 10. Cleanup temp files
for p in glob.glob(f'{BASE}/{FN}.ch*.segments.json'):
    os.remove(p)
for p in glob.glob(f'{BASE}/{FN}.ch*.enrichment.txt'):
    os.remove(p)
for p in [f'{BASE}/{FN}.stitched.txt', f'{BASE}/{FN}.prepared.json']:
    if os.path.exists(p):
        os.remove(p)

print(f'\nDone. {len(final)} claims, {len(all_sub_topics)} sub-topics, {applied} corrections applied.')
