from pathlib import Path
import json,re,zipfile,hashlib,datetime,sys
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else BASE/'build'
OUT.mkdir(parents=True,exist_ok=True)
refs=json.loads((BASE/'references.json').read_text())
links={13:'https://www.mit.edu/~Saltzer/publications/protection/Basic.html',15:'https://www.erights.org/talks/thesis/',21:'https://doi.org/10.1002/j.1538-7305.1948.tb01338.x',24:'https://doi.org/10.6028/NIST.AI.100-1',25:'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng',26:'https://unesdoc.unesco.org/ark:/48223/pf0000386693',27:'https://genai.owasp.org/llm-top-10/',28:'https://sdgs.un.org/2030agenda'}
for r in refs:
 if r['id'] in links:r['url']=links[r['id']]
 if r['id']<=12:r['venue']='arXiv preprint '+r['url'].rsplit('/',1)[-1]
 if r['id']==27:r['title']='OWASP Top 10 for Large Language Model Applications 2025'
# A small original diagram of the enforcement path, not an experimental figure.
im=Image.new('RGB',(1800,520),'white');dr=ImageDraw.Draw(im)
f='/System/Library/Fonts/Supplemental/Arial.ttf';bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
font=ImageFont.truetype(f,34);bf=ImageFont.truetype(bold,38);sf=ImageFont.truetype(f,33)
boxes=[(20,70,495,315),(650,70,1150,315),(1305,70,1780,315)]
texts=[('MODEL AND INPUTS',['Propose typed requests','No standing credentials']),('AUTHORITY SERVICE',['Authenticate and authorise','Recheck before commitment']),('PROTECTED SYSTEMS',['Read or change records','Deliver approved artifacts'])]
for b,(title,lines) in zip(boxes,texts):
 dr.rectangle(b,outline='#414141',width=3,fill='#f7f7f7');cx=(b[0]+b[2])//2
 dr.text((cx,110),title,anchor='mm',font=bf,fill='black')
 for j,line in enumerate(lines):dr.text((cx,195+j*58),line,anchor='mm',font=font,fill='black')
for x1,x2 in [(505,638),(1160,1293)]:
 dr.line((x1,220,x2,220),fill='#333333',width=4);dr.polygon([(x2,220),(x2-20,208),(x2-20,232)],fill='#333333')
dr.text((900,385),'Current contract + lineage + approvals + revocation + budget',anchor='mm',font=font,fill='black')
dr.text((900,455),'AI monitoring may restrict authority; restoration requires an authenticated operator.',anchor='mm',font=sf,fill='black')
im.save(BASE/'enforcement-path.png')
TABLES={
'@RELATED':(['Prior work','Established focus','Contribution examined here'],[
['Capabilities and information flow [13–19]','Access boundaries, attenuation, lineage and independent roles','Composition across an agent task and its failure paths'],
['CaMeL [2]','Control/data separation against prompt injection','Persistent memory, revocation and delivery contracts'],
['AgentSecBench and AgentDyn [10,11]','Agent security evaluation under defined tasks','Named invariant checks, without benchmark ranking'],
['Monitoring [3–8]','Model behaviour and the limits of detection','Monitoring that cannot grant or restore authority'],
['Confinement [20,21]','Information carried through permitted behaviour','Encoder-specific release traces and policy costs']],[1.9,2.15,2.75]),
'@TERMS':(['Term','Meaning','Boundary'],[
['Passport','Approved workload ceiling','Admission'],['Task contract','Scope and purpose of one execution','Each mediated request'],['Capability envelope','Operations currently permitted by intersected rights','Authorisation'],['Attenuation','Delegation only of a subset of existing rights','Agent or service delegation'],['Lineage','Source restrictions retained through derivation','Retrieval, memory and release'],['Release escrow','Approval bound to exact bytes and a recipient','Disclosure'],['Refusal','No protected operation when its checks fail','Every protected interface']],[1.5,3.8,1.5]),
'@EVIDENCE':(['Check','Recorded result','Interpretation'],[
['Controlled comparison','0/7 → 2/7 → 7/7 hostile proposals contained','Unguarded → prompt/allowlist → mediated; not field rates'],
['Six domain profiles','180/180 hostile contained; 58/58 benign completed','Configured profiles, not institutional deployments'],
['Control ablation','Each of 8 removals enables an associated harmful action','Control relevance within those scenarios'],
['Bounded falsification','104,997 attempts; no counterexample found','Only the declared bounded search space'],
['Recorded regression','1,445 tests passed; 37 capability contracts executed','Source-bound local evidence, not production certification'],
['Monitor substitution','No tested prohibited outcome; hostile-monitor benign utility is zero','Authority safety and availability are different properties'],
['Deployment qualification','Controlled host and TLS checks; no production qualification','Institution-specific host and transport evidence remains required']],[1.5,2.7,2.6])}

def xml(tag,**attrs):
 e=OxmlElement('w:'+tag)
 for k,v in attrs.items():e.set(qn('w:'+k),str(v))
 return e

def setfont(style,name,size,bold=False):
 style.font.name=name;style.font.size=Pt(size);style.font.bold=bold;style.font.color.rgb=RGBColor(0,0,0)
 style.element.get_or_add_rPr().append(OxmlElement('w:rFonts')) if style.element.get_or_add_rPr().find(qn('w:rFonts')) is None else None
 fonts=style.element.get_or_add_rPr().find(qn('w:rFonts'))
 for attr in list(fonts.attrib):
  if attr.endswith('Theme'):del fonts.attrib[attr]
 for x in ('ascii','hAnsi','eastAsia'):fonts.set(qn('w:'+x),name)
 for border in list(style.element.iter(qn('w:pBdr'))):border.getparent().remove(border)

def link(p,label,url):
 from docx.opc.constants import RELATIONSHIP_TYPE as RT
 h=OxmlElement('w:hyperlink');h.set(qn('r:id'),p.part.relate_to(url,RT.HYPERLINK,is_external=True))
 r=OxmlElement('w:r');pr=OxmlElement('w:rPr');pr.append(xml('color',val='000000'));r.append(pr);t=OxmlElement('w:t');t.text=label;r.append(t);h.append(r);p._p.append(h)

def reference(doc,r,num):
 p=doc.add_paragraph(style='Bibliography');p.paragraph_format.left_indent=Inches(.28);p.paragraph_format.first_line_indent=Inches(-.28)
 p.add_run(f"[{num}] {r['authors']} ({r['year']}). {r['title'].rstrip('.')}{'' if r['title'].endswith('?') else '.'} {r.get('venue','')}.")
 if r.get('url'):p.add_run(' ');link(p,r['url'],r['url'])
 return p

def table(doc,spec):
 header,rows,widths=spec;t=doc.add_table(rows=1,cols=len(header));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 for c,w in zip(t.columns,widths):c.width=Inches(w)
 pr=t._tbl.tblPr
 border=OxmlElement('w:tblBorders')
 for k in ['top','left','bottom','right','insideH','insideV']:border.append(xml(k,val='single',sz=4,color='D9D9D9'))
 pr.append(border)
 for idx,values in enumerate([header]+rows):
  row=t.rows[0] if idx==0 else t.add_row();row._tr.get_or_add_trPr().append(xml('cantSplit'))
  if idx==0:row._tr.get_or_add_trPr().append(xml('tblHeader'))
  for c,value,w in zip(row.cells,values,widths):
   c.width=Inches(w);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcpr=c._tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
   for pos in ['top','left','bottom','right']:m.append(xml(pos,w=85,type='dxa'))
   tcpr.append(m)
   tcpr.append(xml('shd',fill='E9EEF2' if idx==0 else 'FFFFFF'))
   p=c.paragraphs[0];p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.04
   p.paragraph_format.keep_with_next=idx==0
   r=p.add_run(value);r.font.size=Pt(10);r.bold=idx==0
 return t

def deterministic_save(doc,path):
 tmp=path.with_suffix('.tmp.docx');doc.save(tmp)
 with zipfile.ZipFile(tmp) as zin,zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as zout:
  for name in sorted(zin.namelist()):
   info=zipfile.ZipInfo(name,date_time=(2026,9,19,12,0,0));info.compress_type=zipfile.ZIP_DEFLATED;zout.writestr(info,zin.read(name))
 tmp.unlink()

def build(kind):
 full=kind=='full-paper';text=(BASE/(kind+'.md')).read_text();d=Document();sec=d.sections[0]
 sec.page_width=Inches(8.5);sec.page_height=Inches(11);sec.top_margin=sec.bottom_margin=Inches(.72);sec.left_margin=sec.right_margin=Inches(.85)
 sec.footer_distance=Inches(.32)
 setfont(d.styles['Normal'],'Times New Roman',11)
 norm=d.styles['Normal'].paragraph_format;norm.line_spacing=1.08;norm.space_after=Pt(6);norm.widow_control=True
 for sty,size in [('Title',17),('Heading 1',12),('Heading 2',11)]:
  setfont(d.styles[sty],'Times New Roman',size,True)
  pf=d.styles[sty].paragraph_format;pf.space_before=Pt(11 if sty!='Title' else 0);pf.space_after=Pt(5);pf.keep_with_next=True
 setfont(d.styles['Caption'],'Times New Roman',9.5);d.styles['Caption'].font.italic=False
 d.styles.add_style('Bibliography',1)
 setfont(d.styles['Bibliography'],'Times New Roman',9.5)
 d.styles['Bibliography'].paragraph_format.space_after=Pt(2);d.styles['Bibliography'].paragraph_format.line_spacing=1.0
 p=sec.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
 text=re.sub(r'^(#{2,3} [^\n]+)\n',r'\1\n\n',text,flags=re.M)
 blocks=text.strip().split('\n\n'); skip=False
 for idx,b in enumerate(blocks):
  if skip:skip=False;continue
  if b.startswith('# '):
   lines=b.splitlines();p=d.add_paragraph(lines[0][2:],'Title')
   if len(lines)>1 and lines[1]!='@AUTHOR':
    p=d.add_paragraph(lines[1]);p.runs[0].italic=True;p.paragraph_format.keep_with_next=True
   if '@AUTHOR' not in b:continue
   b='@AUTHOR'
  if b=='@AUTHOR':
   p=d.add_paragraph('Rachana (Gen) Srivastava');p.runs[0].bold=True;p.paragraph_format.space_after=Pt(2);p.paragraph_format.keep_with_next=True
   p=d.add_paragraph('UNU Macau AI Conference 2026' + (' | Extended abstract' if not full else ''))
   p.runs[0].font.size=Pt(9.5);p.paragraph_format.space_after=Pt(10);p.paragraph_format.keep_with_next=True
  elif b in TABLES:
   caption=blocks[idx+1];p=d.add_paragraph(caption,'Caption');p.paragraph_format.keep_with_next=True
   table(d,TABLES[b]);d.add_paragraph().paragraph_format.space_after=Pt(0);skip=True
  elif b=='@REFERENCES':
   selected=refs if full else [refs[i-1] for i in [13,16,2,20,24,26,28]]
   for j,r in enumerate(selected,1):reference(d,r,j)
  elif b.startswith('### '):d.add_paragraph(b[4:],'Heading 2')
  elif b.startswith('## '):
   head=b[3:];p=d.add_paragraph(head,'Heading 1')
   if head=='References':p.paragraph_format.page_break_before=full
  elif b.startswith('Property 1'):
   p=d.add_paragraph(b);p.runs[0].bold=True;p.paragraph_format.keep_with_next=True
  elif b.startswith('O(s,m,r)') or b.startswith('L(P,f)'):
   # Native Word math avoids Unicode layout and italicisation ambiguities.
   expr=('O(s,m,r) ⊆ A(s)' if b.startswith('O') else 'L(P,f) = log₂ |{T(P,f,z) : z ∈ Z}|');n='1' if b.startswith('O') else '2'
   p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(8)
   math=OxmlElement('m:oMath');mr=OxmlElement('m:r');mt=OxmlElement('m:t');mt.text=expr;mr.append(mt);math.append(mr);p._p.append(math);p.add_run('   ('+n+')')
  else:
   p=d.add_paragraph(b)
   if b.startswith('Keywords:'):p.runs[0].font.size=Pt(9.5)
   if b.startswith('Let s denote') or b.startswith('Let Z be'):p.paragraph_format.keep_with_next=True
  if full and b.startswith('Equation (1) is a specification'):
   p=d.add_paragraph();p.add_run().add_picture(str(BASE/'enforcement-path.png'),width=Inches(6.8));p.paragraph_format.keep_with_next=True
   sh=d.inline_shapes[-1];sh._inline.docPr.set('descr','Models submit typed proposals to an independent enforcement service. The service checks current authority before access to protected institutional systems; monitoring may restrict but not restore rights.')
   p=d.add_paragraph('Figure 1. Enforcement path. The separation shown is an architectural requirement; host isolation and adapter correctness require deployment qualification.','Caption')
 d.core_properties.author='Rachana (Gen) Srivastava';d.core_properties.title='Trust by Construction for Secure Agentic Workflows in Learning Institutions';d.core_properties.subject='V-17 | '+('Full technical paper' if full else 'Extended abstract');d.core_properties.version='17';d.core_properties.created=datetime.datetime(2026,9,19,12);d.core_properties.modified=datetime.datetime(2026,9,19,12)
 name='Trust_by_Construction_V17.docx' if full else 'Trust_by_Construction_V17_Extended_Abstract.docx'
 path=OUT/name;deterministic_save(d,path)
 # Citation coverage includes table content and excludes references.
 before=text.split('## References')[0]; cited=set()
 for group in re.findall(r'\[([0-9,– -]+)\]',before):
  for piece in group.split(','):
   bounds=re.split('[–-]',piece.strip());cited.update(range(int(bounds[0]),int(bounds[-1])+1))
 expected=set(range(1,29 if full else 8));assert cited==expected,(kind,cited^expected)
 alltext='\n'.join(''.join(e.itertext()) for e in [])
 xmltext=' '.join(t.text or '' for t in d._element.iter(qn('w:t')))
 bodytext=xmltext.split('References')[0]
 info={'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body_words_including_title_author_headings_captions_tables':len(bodytext.split()),'total_words_including_references':len(xmltext.split()),'references':len(expected),'synthetic_mentions':xmltext.lower().count('synthetic')}
 return info
stats=[build('full-paper'),build('extended-abstract')];(BASE/'release-stats.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2))
