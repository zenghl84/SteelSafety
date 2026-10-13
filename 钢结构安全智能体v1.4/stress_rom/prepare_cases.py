"""Generate reversible MIDAS MGT trial copies; does not run MIDAS."""
from pathlib import Path
from decimal import Decimal
import argparse
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
CASES = [('case_080', .8, 'train'), ('case_100', 1., 'train'),
         ('case_120', 1.2, 'train'), ('case_090', .9, 'test'),
         ('case_110', 1.1, 'test')]


def decode_mgt(raw):
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise ValueError('无法识别 MGT 编码。')


def scaled_copy(raw, factor, load_case='施工活荷载', group='施工荷载组18'):
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError('本试验要求正的有限荷载倍率。')
    text, encoding = decode_mgt(raw)
    out, changes = [], []
    section = current_load = ''
    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        body = line.rstrip('\r\n')
        newline = line[len(body):]
        data, separator, comment = body.partition(';')
        clean = data.strip()
        if clean.startswith('*'):
            section = clean.split(',')[0].split()[0]
            if section == '*USE-STLD':
                current_load = clean.split(',', 1)[1].strip()
        elif clean and section == '*CONLOAD' and current_load == load_case:
            fields = data.split(',')
            if len(fields) >= 8 and fields[7].strip() == group:
                before = [Decimal(v.strip()) for v in fields[1:7]]
                if not all(v.is_finite() for v in before):
                    raise ValueError(f'第 {line_number} 行荷载不是有限数值。')
                after = [v * Decimal(str(factor)) for v in before]
                changes.append(dict(line=line_number, nodes=fields[0].strip(),
                                    before=list(map(float, before)),
                                    after=list(map(float, after))))
                if factor != 1.0:
                    for k, value in enumerate(after, 1):
                        token = fields[k]
                        leading = token[:len(token) - len(token.lstrip())]
                        trailing = token[len(token.rstrip()):]
                        fields[k] = leading + format(value, 'f') + trailing
                    line = ','.join(fields) + separator + comment + newline
        out.append(line)
    if not changes:
        raise ValueError('未找到指定工况与荷载组；没有生成替代模型。')
    # Preserve original bytes exactly for the reference case, including BOM.
    encoded = raw if factor == 1.0 else ''.join(out).encode(encoding)
    return encoded, changes


def prepare(root=ROOT):
    root = Path(root)
    raw = (root / 'source/model.mgt').read_bytes()
    case_dir = root / 'midas_cases'
    case_dir.mkdir(exist_ok=True)
    manifest, audits = [], []
    for name, factor, split in CASES:
        generated, changes = scaled_copy(raw, factor)
        if len(changes) != 83:
            raise ValueError('本程序针对已核对的 83 条荷载；当前模型发生变化，请重新核对。')
        target = case_dir / f'{name}.mgt'
        if target.exists() and target.read_bytes() != generated:
            raise FileExistsError(f'{target} 已有不同内容；请另存项目后再生成。')
        target.write_bytes(generated)
        manifest.append(dict(case_id=name, lambda_value=factor, split=split,
                             result_base=f'results/{name}_CS18',
                             reference_base='results/CS13_reference',
                             midas_file=f'midas_cases/{name}.mgt'))
        audits.append(dict(case_id=name, lambda_value=factor,
                           sha256=hashlib.sha256(generated).hexdigest(),
                           changed_load_records=len(changes),
                           original_total_fz_N=sum(r['before'][2] for r in changes),
                           new_total_fz_N=sum(r['after'][2] for r in changes),
                           records=changes))
    manifest_path = root / 'cases.csv'
    if manifest_path.exists():
        existing = list(csv.DictReader(manifest_path.open(encoding='utf-8-sig', newline='')))
        if existing != [{k: str(v) for k, v in r.items()} for r in manifest]:
            raise FileExistsError('cases.csv 已被修改；请保留该文件并另存项目后再生成。')
    with manifest_path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    report = dict(source_sha256=hashlib.sha256(raw).hexdigest(),
                  parameter='施工活荷载 / 施工荷载组18 / 节点荷载倍率',
                  stage='CS18', note='仅生成文本模型；尚未在 MIDAS 中分析。', cases=audits)
    (root / 'case_generation_audit.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已准备 5 份 MGT 工况副本。每份保留原模型，指定荷载组按倍率变化。')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    prepare(args.root)
