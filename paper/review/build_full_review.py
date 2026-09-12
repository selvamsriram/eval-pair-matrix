#!/usr/bin/env python3
"""Highlight final wording changed from submission, preserving the clean PDF."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, NameObject

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / 'paper'
BUILD = ROOT / 'tmp/pdfs/yellow-only'
COMMIT = '1554258'
CLEAN = ROOT / 'output/pdf/eval-pair-matrix-camera-ready.pdf'
OUTPUT = ROOT / 'output/pdf/eval-pair-matrix-all-changes.pdf'
FILES = ('main_body.tex', 'references.tex', 'appendix_content.tex')
STRUCTURAL = re.compile(r'^\s*\\(?:begin|end|captionsetup|vspace|FloatBarrier|label|centering|scriptsize|small|footnotesize|raggedright|toprule|midrule|bottomrule|renewcommand)\b')
WRAPPER = re.compile(r'^(\s*\\(?:paragraph|subsection|section\*?|caption|captionof\{[^}]+\})\{)(.*)(\})$')


def tokens(text):
    """Keep commands with their arguments and inline math indivisible."""
    out=[]; i=0
    while i<len(text):
        start=i
        if text[i].isspace():
            while i<len(text) and text[i].isspace(): i+=1
        elif text[i]=='$':
            i+=1
            while i<len(text) and (text[i]!='$' or text[i-1]=='\\'): i+=1
            i+=1
        elif text[i]=='\\':
            m=re.match(r'\\(?:[A-Za-z]+\*?|.)',text[i:]);i+=len(m[0])
            while i<len(text) and text[i] in '{[':
                opening=text[i]; closing='}' if opening=='{' else ']'; depth=1;i+=1
                while i<len(text) and depth:
                    if text[i-1]!='\\':
                        if text[i]==opening:depth+=1
                        elif text[i]==closing:depth-=1
                    i+=1
        else:
            while i<len(text) and not text[i].isspace() and text[i] not in '$\\':i+=1
        out.append(text[start:i])
    return out


def mark_diff(old,new):
    a,b=tokens(old),tokens(new);marked=[]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        part=''.join(b[k:l])
        if tag in ('insert','replace') and part.strip():
            left=len(part)-len(part.lstrip());right=len(part.rstrip())
            marked.append(part[:left]+r'\diffmark{'+part[left:right]+'}'+part[right:])
        else:marked.append(part)
    return ''.join(marked)


def mark_line(old,new):
    if not new.strip() or STRUCTURAL.match(new):return new
    # Keep the alignment command first in its cell; color only its contents.
    table_wrapper=re.compile(r'^(\s*\\multicolumn\{[^}]+\}\{.*\}\{)(.*)(\}\s*\\\\)$')
    m=table_wrapper.fullmatch(new)
    if m:
        previous=table_wrapper.fullmatch(old)
        return m[1]+mark_diff(previous[2] if previous else '',m[2])+m[3]
    m=WRAPPER.fullmatch(new)
    if m:
        previous=WRAPPER.fullmatch(old)
        return m[1]+mark_diff(previous[2] if previous else '',m[2])+m[3]
    if ' & ' in new and new.endswith(r'\\'):
        a=old[:-2].split('&') if old else ['']*len(new[:-2].split('&'))
        b=new[:-2].split('&')
        if len(a)!=len(b):raise ValueError('Changed table structure requires review')
        return '&'.join(mark_diff(x,y) for x,y in zip(a,b))+r'\\'
    return mark_diff(old,new)


def color_sources():
    changes=[];patch=[]
    for name in FILES:
        old=subprocess.check_output(['git','show',f'{COMMIT}:paper/{name}'],cwd=ROOT).decode()
        new=(PAPER/name).read_text();a,b=old.splitlines(),new.splitlines();output=[]
        patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='submitted/'+name,tofile='camera-ready/'+name))
        for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
            if tag=='equal':output.extend(b[k:l]);continue
            changes.append(dict(file=name,old_line=i+1,new_line=k+1,old='\n'.join(a[i:j]),new='\n'.join(b[k:l]),kind=tag))
            if tag=='delete':continue
            if tag=='insert':output.extend(mark_line('',line) for line in b[k:l]);continue
            if j-i!=l-k:
                if j-i!=1:raise ValueError(('Unaligned source replacement',name,i,j,k,l))
                # A revised paragraph followed by newly added paragraphs.
                best=max(range(k,l),key=lambda n:difflib.SequenceMatcher(None,a[i],b[n],autojunk=False).ratio())
                output.extend(mark_line(a[i] if n==best else '',b[n]) for n in range(k,l))
                continue
            output.extend(mark_line(x,y) for x,y in zip(a[i:j],b[k:l]))
        (BUILD/name.replace('.tex','_marked.tex')).write_text('\n'.join(output)+'\n')
    wrapper=(PAPER/'camera_ready.tex').read_text()
    preamble=r'''
\definecolor{DiffMark}{rgb}{1,0,1}
\DeclareRobustCommand{\diffmark}[1]{{\hypersetup{urlcolor=DiffMark,citecolor=DiffMark,linkcolor=DiffMark}\color{DiffMark}#1}}
\pdfstringdefDisableCommands{\def\diffmark#1{#1}}
'''
    wrapper=wrapper.replace(r'\begin{document}',preamble+'\n'+r'\begin{document}')
    # Define the marker before author content is executed by maketitle.
    wrapper=wrapper.replace('Sriram Selvam \\and Anneswa Ghosh',r'\diffmark{Sriram Selvam} \and \diffmark{Anneswa Ghosh}')
    wrapper=wrapper.replace('  Independent Researchers \\\\',r'  \diffmark{Independent Researchers} \\')
    wrapper=wrapper.replace(r'\texttt{\{selvamsriram,anneswaghosh\}@gmail.com}',r'\diffmark{\texttt{\{selvamsriram,anneswaghosh\}@gmail.com}}')
    for name in FILES:wrapper=wrapper.replace('\\input{'+name[:-4]+'}','\\input{'+name[:-4]+'_marked}')
    (BUILD/'marked.tex').write_text(wrapper)
    env=dict(os.environ);env['TEXINPUTS']=str(BUILD)+os.pathsep+env.get('TEXINPUTS','')
    for n in range(1,4):
        result=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','-file-line-error',f'-output-directory={BUILD}',str(BUILD/'marked.tex')],cwd=PAPER,env=env,capture_output=True,text=True)
        (BUILD/f'build-{n}.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise SystemExit('\n'.join((result.stdout+result.stderr).splitlines()[-50:]))
    (PAPER/'review/submitted-to-camera-ready.patch').write_text(''.join(patch))
    return changes


def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    clean_hash=hashlib.sha256(CLEAN.read_bytes()).hexdigest()
    changes=color_sources(); rectangles=[]
    with pdfplumber.open(CLEAN) as clean, pdfplumber.open(BUILD/'marked.pdf') as marked:
        if len(clean.pages)!=len(marked.pages):raise ValueError('Marker compilation changed pagination')
        for number,(cp,mp) in enumerate(zip(clean.pages,marked.pages)):
            if len(cp.chars)!=len(mp.chars):raise ValueError(('Marker changed glyph count',number+1,len(cp.chars),len(mp.chars)))
            selected=[]
            for cc,mc in zip(cp.chars,mp.chars):
                if cc['text']!=mc['text'] or any(abs(cc[k]-mc[k])>0.03 for k in ('x0','x1','top','bottom')):
                    raise ValueError(('Marker changed glyph or position',number+1,cc['text'],mc['text'],cc['x0'],mc['x0']))
                if tuple(mc.get('non_stroking_color') or ())==(1,0,1) and cc['text'].strip():selected.append(cc)
            spans=[]
            for c in sorted(selected,key=lambda c:(round(c['top'],1),c['x0'])):
                if spans and abs(spans[-1][1]-c['top'])<0.5 and abs(spans[-1][3]-c['bottom'])<0.5 and -0.5<=c['x0']-spans[-1][2]<4:
                    spans[-1][0]=min(spans[-1][0],c['x0'])
                    spans[-1][1]=min(spans[-1][1],c['top'])
                    spans[-1][2]=max(spans[-1][2],c['x1'])
                    spans[-1][3]=max(spans[-1][3],c['bottom'])
                else:spans.append([c['x0'],c['top'],c['x1'],c['bottom']])
            assert all(any(x0<=c['x0'] and x1>=c['x1'] and top<=c['top'] and bottom>=c['bottom']
                           for x0,top,x1,bottom in spans) for c in selected)
            rectangles.append(spans)
    reader=PdfReader(CLEAN);writer=PdfWriter();writer.clone_document_from_reader(reader)
    for page,spans in zip(writer.pages,rectangles):
        if not spans:continue
        h=float(page.mediabox.height)
        stream=DecodedStreamObject()
        commands=['q','1 0.949 0.518 rg']
        for x0,top,x1,bottom in spans:
            commands.append(f'{x0-0.15:.4f} {h-bottom:.4f} {x1-x0+0.3:.4f} {bottom-top:.4f} re f')
        commands.append('Q');stream.set_data(('\n'.join(commands)+'\n').encode())
        contents=page.raw_get('/Contents')
        original=contents.get_object()
        refs=list(original) if isinstance(original,ArrayObject) else [contents]
        page[NameObject('/Contents')]=ArrayObject([writer._add_object(stream),*refs])
    with OUTPUT.open('wb') as f:writer.write(f)
    check=PdfReader(OUTPUT)
    assert len(check.pages)==len(reader.pages)
    assert all(a.extract_text()==b.extract_text() for a,b in zip(reader.pages,check.pages))
    assert hashlib.sha256(CLEAN.read_bytes()).hexdigest()==clean_hash
    manifest={'baseline_commit':subprocess.check_output(['git','rev-parse',COMMIT],cwd=ROOT).decode().strip(),
        'submitted_pdf_sha256':'f481908bb3a734f038605f655a4d014a2bd57a35a76bb67fb264a39d39373dac',
        'clean_pdf_sha256':clean_hash,'output_pdf_sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'presentation':'Final camera-ready PDF with yellow underlays behind inserted/replaced text and new reference links. No old text, arrows, cover, headers, page numbers, or reflow. Deletions and layout-only changes have no text to highlight.',
        'pages':len(reader.pages),'highlight_rectangles_by_page':[len(s) for s in rectangles],
        'glyph_positions_verified':True,'extracted_text_identical_to_clean':True,'changes':changes}
    (PAPER/'review/all_changes.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Built',OUTPUT,'with',len(reader.pages),'unchanged pages and',sum(map(len,rectangles)),'yellow spans.')


if __name__=='__main__':main()
