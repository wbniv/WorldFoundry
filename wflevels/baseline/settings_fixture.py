"""Generate explicit OAS sources and a complete descriptor coverage manifest.

OAS goes through oas2oad/prep; no runtime or global actor packing is changed.
Unsupported presentations are recorded, not presented as implemented widgets.
"""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
TYPES=['FIXED16','FIXED32','INT8','INT16','INT32','STRING','OBJECT_REFERENCE','FILENAME','PROPERTY_SHEET','NOINSTANCES','NOMESH','SINGLEINSTANCE','TEMPLATE','EXTRACTCAMERA','CAMERA_REFERENCE','LIGHT_REFERENCE','ROOM','COMMONBLOCK','ENDCOMMON','MESHNAME','XDATA','EXTRACT_CAMERA','EXTRACTCAMERANEW','WAVEFORM','CLASS_REFERENCE','GROUP_START','GROUP_STOP','EXTRACTLIGHT','SHORTCUT']
SHOW=['N_A','NUMBER','SLIDER','TOGGLE','DROPMENU','RADIOBUTTONS','HIDDEN','COLOR','CHECKBOX','MAILBOX','COMBOBOX','TEXTEDITOR','FILENAME']
WIDTH={'INT8':1,'INT16':2,'INT32':4,'FIXED16':2,'FIXED32':4,'STRING':32,'OBJECT_REFERENCE':4,'CAMERA_REFERENCE':4,'LIGHT_REFERENCE':4,'CLASS_REFERENCE':4}

def create():
    from runtime_options_fixture import write_manifest, sheet
    runtime_fields=write_manifest(HERE)
    runtime_lines,runtime_bindings=sheet(runtime_fields)
    fields=[]
    def field(t,show,semantic,lo=0,hi=10,default=0,choices='',initial=None,**metadata):
        id=len(fields)+1;key=f'{semantic}_{t}_{show}_{id}'
        fields.append(dict(id=id,key=key,type=t,button_type=TYPES.index(t),show=show,show_code=(128 if show.startswith('VECTOR_') else 0)+SHOW.index(show.removeprefix('VECTOR_')),semantic=semantic,min=lo,max=hi,default=default,choices=choices,width=WIDTH.get(t,0),initial=initial))
        fields[-1].update(metadata)
        return key
    for t in ['INT8','INT16','INT32']:
        for show in ['N_A','NUMBER','SLIDER','HIDDEN']:field(t,show,'Signed',-12,12,-3)
        for show in ['N_A','NUMBER','SLIDER','TOGGLE','DROPMENU','RADIOBUTTONS','COMBOBOX','HIDDEN']:field(t,show,'Enum',3,5,4,'Low|Medium|High')
        for labelled in [False,True]:
            for show in (['CHECKBOX','TOGGLE','RADIOBUTTONS','HIDDEN'] if labelled else ['CHECKBOX','TOGGLE','HIDDEN']):field(t,show,'BooleanLabels' if labelled else 'Boolean',0,1,1,'False|True' if labelled else '')
    for t,scale in [('FIXED16',256),('FIXED32',65536)]:
        for show in ['N_A','NUMBER','SLIDER','HIDDEN']:field(t,show,'Fraction',-2*scale,2*scale,scale//4,scale=scale)
    for show in ['MAILBOX','HIDDEN']:field('INT32',show,'Mailbox',0,159,120)
    for show in ['COLOR','HIDDEN']:field('INT32',show,'Colour',0,0xFFFFFF,0x42A5F5)
    for show in ['N_A','NUMBER','HIDDEN']:field('STRING',show,'Text',0,31,initial='Baseline' if show!='NUMBER' else '4294967295',rule='uint32-decimal' if show=='NUMBER' else None)
    field('STRING','TEXTEDITOR','Multiline',0,63,initial='First line\nSecond line',width=64,multiline=True)
    field('STRING','COMBOBOX','TextSuggestions',0,31,choices='Alpha|Beta',initial='Custom')
    field('STRING','FILENAME','PathText',0,31,initial='player.iff',filter='*.iff')
    for t in ['FILENAME','MESHNAME']:
        for show in ['N_A','FILENAME','HIDDEN']:field(t,show,'Asset',initial='player.iff',filter='*.iff',width=80)
    for t in ['OBJECT_REFERENCE','CAMERA_REFERENCE','LIGHT_REFERENCE','CLASS_REFERENCE']:
        for show in ['N_A','COMBOBOX','HIDDEN']:field(t,show,'Reference',initial='UnitCube' if t=='OBJECT_REFERENCE' else 'Camera' if t=='CAMERA_REFERENCE' else 'Directional' if t=='LIGHT_REFERENCE' else 'statplat',typed_target=t)
    for show in ['N_A','TEXTEDITOR','DROPMENU','COMBOBOX','HIDDEN']:field('XDATA',show,'Annotation',choices='Alpha|Beta' if show in ['DROPMENU','COMBOBOX'] else '',initial='Baseline annotation',conversion_action=0,width=0,multiline=True)
    for show in ['VECTOR_N_A','HIDDEN']:field('OBJECT_REFERENCE',show,'VectorReference',initial='Player',modifier='VECTOR')
    for show in ['VECTOR_N_A','VECTOR_NUMBER','VECTOR_SLIDER','HIDDEN']:
        for axis in 'XYZ':field('FIXED32',show,'Direction'+axis,-65536,65536,65536 if axis=='X' else 0,scale=65536,vector_group='Direction_'+show,vector_component=axis)
    # Semantic variants beyond a type/presentation matrix.
    field('INT32','RADIOBUTTONS','NegativeEnum',-2,0,-1,'Low|Medium|High')
    field('INT32','RADIOBUTTONS','ManyChoices',0,11,4,'|'.join('Choice '+str(i) for i in range(12)))
    field('INT32','NUMBER','ReadOnly',-10,10,0,readonly=True)
    field('STRING','N_A','ReadOnlyText',0,31,initial='Read only',readonly=True)
    field('INT32','CHECKBOX','EnableDependent',0,1,0)
    field('FIXED32','NUMBER','Conditional',0,65536,32768,scale=65536,enable_expression=fields[-1]['key']+'==1')
    exclusions={t:'Compiler/export directive or authoring data; no editable instance scalar' for t in TYPES if t not in {f['type'] for f in fields} and t not in ['PROPERTY_SHEET','GROUP_START','GROUP_STOP']}
    manifest=dict(version=1,fields=fields,structural_types=['PROPERTY_SHEET','GROUP_START','GROUP_STOP'],exclusions=exclusions,
        negative_cases=['enum range/choice-count mismatch','checkbox with five values','invalid defaults/ranges','duplicate IDs','wrong reference type','missing/deleted target','disallowed asset','overlength UTF-8 text','unknown type/hint'],
        boundary_cases=['width signed limits','smallest fixed step','empty text','byte/character length divergence','hidden retention','conditional draft dependency','two-instance isolation','stale revisions','long help','empty/all-choice sections'],
        source_vs_binary_audit='Compare compiled OAD, not macro names: TYPEENTRYSTRING is XData; Notes macro currently compiles N_A despite its TEXTEDITOR argument.',
        implementation_gaps=['Generic in-game opening/selection of non-plant property objects requires a reviewed engine API; catalog is attached but not interactively reachable yet.', 'Enable expressions, asset filters, typed-reference tags and vector grouping are not fully retained by current catalog cooker.', 'String combo/dropdown hints and grouped vectors are not implemented runtime controls.'],
        status='Sources and compiled/cooked coverage are verifiable separately; interactive acceptance remains pending')
    for f in fields:
        f['provenance']='synthetic compatibility fixture'
        if f['semantic']=='Text' and f['show']=='NUMBER':f['provenance']='matches planted-tank Seed storage/hint'
        if f['semantic']=='VectorReference' and f['show']=='VECTOR_N_A':f['provenance']='matches shipped camshot Follow/Target modifiers'
        if f['semantic']=='Annotation' and f['show']=='DROPMENU':f['provenance']='matches shipped test String type/hint'
        if f['show']=='HIDDEN':f['expected']='omitted; no visible widget acceptance'
        elif f['type'] in ['FILENAME','MESHNAME','OBJECT_REFERENCE','CAMERA_REFERENCE','LIGHT_REFERENCE','CLASS_REFERENCE']:f['expected']='read-only; picker unsupported'
        elif f.get('vector_group') or f.get('modifier'):f['expected']='modifier/group interpretation unsupported; preserve source metadata'
        elif f.get('enable_expression'):f['expected']='conditional evaluation unsupported; keep out of runtime catalog'
        elif f['show']=='COMBOBOX' and f['type'] in ['STRING','XDATA']:f['expected']='editable suggestions unsupported; text fallback is not pair acceptance'
        else:f['expected']='verify actual TV/phone presentation and typed readback; not yet accepted'
    def descriptor(f):
        # Direct descriptor spelling permits narrow catalog fixtures without
        # enabling narrow legacy actor-layout macros.
        t=f['type'];name=f['key'];show=f['show_code'];length=f['width'] if t in ['STRING','FILENAME','MESHNAME'] else 80 if t=='XDATA' else 12 if 'REFERENCE' in t else 0
        union='{0,0,"'+name+'","'+f.get('enable_expression','1')+'"}'
        filt='"Assets\\0'+f['filter']+'\\0\\0"' if f.get('filter') else '""'
        return '{'+f'{f["button_type"]},"{name}",{f["min"]},{f["max"]},{f["default"]},{length},"{f["choices"]}",{show},-1,-1,"Baseline {f["semantic"]}",'+union+','+filt+'},'
    from memory_settings_fixture import sheet as memory_sheet
    memory_lines, memory_bindings = memory_sheet()
    def write(name, selected, gallery):
        lines=['@* Generated by settings_fixture.py; explicit baseline-only catalog schema.','TYPEHEADER(BaselineSettings)']
        lines+=['PROPERTY_SHEET_HEADER('+('Coverage' if gallery else 'Sample Settings')+',1)','GROUP_START(Values)']
        lines += [descriptor(f) for f in selected]
        lines += ['GROUP_STOP()','PROPERTY_SHEET_FOOTER','PROPERTY_SHEET_HEADER(Empty section,0)','GROUP_START(Empty group)','GROUP_STOP()','PROPERTY_SHEET_FOOTER']
        lines += runtime_lines + memory_lines + ['TYPEFOOTER']
        (HERE/(name+'.oas')).write_text('\n'.join(lines)+'\n')
        bindings={}
        for f in selected:
            if f['show']=='HIDDEN' or f.get('enable_expression'):continue
            b=dict(id=f['id'])
            for key in ['initial','rule','readonly','multiline']:
                if f.get(key) is not None:b[key]=f[key]
            if f['type'] in ['STRING','XDATA']:b['max_length']=f['width']-1 if f['type']=='STRING' else 80
            bindings[f['key']]=b
        assert not ({b['id'] for b in bindings.values()} & {b['id'] for b in runtime_bindings.values()})
        bindings.update(runtime_bindings)
        assert not ({b['id'] for b in bindings.values()} & {b['id'] for b in memory_bindings.values()})
        bindings.update(memory_bindings)
        (HERE/(name+'-bindings.json')).write_text(json.dumps(dict(version=1,owner='SampleSettings',title='Baseline settings',fields=bindings),indent=2)+'\n')
    write('settings-gallery',fields,True)
    sample=[next(f for f in fields if f['semantic']==sem and f['type']==t and f['show']==show) for sem,t,show in [('Signed','INT32','NUMBER'),('Fraction','FIXED32','SLIDER'),('Enum','INT32','RADIOBUTTONS'),('Boolean','INT32','CHECKBOX'),('Text','STRING','N_A')]]
    write('settings',sample,False)
    assert set(TYPES)=={f['type'] for f in fields}|set(exclusions)|set(manifest['structural_types'])
    assert set(range(13)) <= {f['show_code']&127 for f in fields}
    (HERE/'settings-coverage.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    m=create();print('OAS/OAD coverage:',len(m['fields']),'fields;',len(m['exclusions']),'excluded descriptor types')
