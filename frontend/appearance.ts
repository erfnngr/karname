type Appearance={changed:{connect:(fn:(raw:string)=>void)=>void};current:(fn:(raw:string)=>void)=>void};

const modeVarCache:Record<string,Record<string,string>>={};
let activePresetKey='default';
let optimisticMode:boolean|null=null;
let optimisticUntil=0;
let reconcileCurrent:(()=>void)|null=null;

export function reconcileAppearance(){
  optimisticMode=null;
  reconcileCurrent?.();
}

export function instantToggleAppearance(nextDark:boolean){
  optimisticMode=nextDark;
  optimisticUntil=Date.now()+2000;
  const root=document.documentElement;
  root.classList.toggle('dark',nextDark);
  root.style.colorScheme=nextDark?'dark':'light';
  const cached=modeVarCache[`${activePresetKey}:${nextDark?'dark':'light'}`]||modeVarCache[nextDark?'dark':'light'];
  if(cached){
    for(const [k,v] of Object.entries(cached))root.style.setProperty(k,v);
    return;
  }
  const fallback:Record<string,string>=nextDark
    ?{'--color-background':'#0b1220','--color-foreground':'#f1f5f9','--color-card':'#141e30','--color-border':'#263449','--color-muted':'#1f2d42','--color-muted-foreground':'#94a3b8','--color-accent':'#253650','--glass-bg':'rgba(18, 30, 48, 0.54)','--glass-bg-strong':'rgba(18, 30, 48, 0.68)','--glass-bg-subtle':'rgba(24, 36, 56, 0.44)'}
    :{'--color-background':'#f4f7fb','--color-foreground':'#132238','--color-card':'#ffffff','--color-border':'#dbe4f0','--color-muted':'#eef3f8','--color-muted-foreground':'#64748b','--color-accent':'#e2ebf5','--glass-bg':'rgba(255, 255, 255, 0.50)','--glass-bg-strong':'rgba(255, 255, 255, 0.64)','--glass-bg-subtle':'rgba(255, 255, 255, 0.48)'};
  for(const [k,v] of Object.entries(fallback))root.style.setProperty(k,v);
}

export function connectAppearance(native?:Appearance){
  if(!native)return;
  const apply=(raw:string)=>{
    try{
      const value=JSON.parse(raw);
      const root=document.documentElement;
      const dark=!!value.dark;
      if(optimisticMode!==null && Date.now()<optimisticUntil && dark!==optimisticMode)return;
      optimisticMode=null;
      root.classList.toggle('dark',dark);
      root.style.colorScheme=dark?'dark':'light';

      const c=value.colors||{};
      const setVar=(name:string,fallback:string)=>{
        const candidate=c[name];
        const color=typeof candidate==='string'&&/^#[0-9a-fA-F]{6}$/.test(candidate)?candidate:fallback;
        return color;
      };

      const bg=setVar('bg',dark?'#0b1220':'#f4f7fb');
      const panel=setVar('panel',dark?'#141e30':'#ffffff');
      const text=setVar('text',dark?'#f1f5f9':'#132238');
      const muted=setVar('muted',dark?'#94a3b8':'#64748b');
      const border=setVar('border',dark?'#263449':'#dbe4f0');
      const field=setVar('field',dark?'#182438':'#ffffff');
      const button=setVar('button',dark?'#1f2d42':'#eef3f8');
      const hover=setVar('hover',dark?'#253650':'#e2ebf5');
      const accent=setVar('accent','#1b6ca8');
      const accentText=setVar('accent_text','#ffffff');

      const tokens:Record<string,string>={
        '--color-background':bg,
        '--color-foreground':text,
        '--color-card':panel,
        '--color-card-foreground':text,
        '--color-popover':panel,
        '--color-popover-foreground':text,
        '--color-muted':button,
        '--color-muted-foreground':muted,
        '--color-border':border,
        '--color-input':field,
        '--color-secondary':button,
        '--color-secondary-foreground':text,
        '--color-accent':hover,
        '--color-accent-foreground':text,
        '--color-primary':accent,
        '--color-primary-foreground':accentText,
        '--color-ring':accent,
        '--color-sidebar':panel,
        '--color-sidebar-foreground':text,
        '--color-sidebar-border':border,
        '--color-sidebar-accent':hover,
        '--color-sidebar-accent-foreground':text,
        '--color-sidebar-ring':accent,
        '--app-bg':bg,
        '--app-panel':panel,
        '--app-text':text,
        '--app-muted':muted,
        '--app-border':border,
        '--app-accent':accent,
        '--app-accent-text':accentText,
      };
      const tokensObj=(value.tokens&&typeof value.tokens==='object'?value.tokens:{}) as Record<string,unknown>;
      const radNum=typeof tokensObj.radius==='number'?Math.max(0,Math.min(28,tokensObj.radius)):NaN;
      if(!Number.isNaN(radNum)){
        tokens['--card-radius']=`${radNum}px`;
        tokens['--radius-lg']=`${radNum}px`;
      }else{
        root.style.removeProperty('--card-radius');
      }
      const alphaNum=typeof tokensObj.glass_alpha==='number'?Math.max(20,Math.min(100,tokensObj.glass_alpha)):NaN;
      const toRgba=(hex:string,alpha:number)=>{
        const r=parseInt(hex.slice(1,3),16);
        const g=parseInt(hex.slice(3,5),16);
        const b=parseInt(hex.slice(5,7),16);
        return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(2)})`;
      };
      const a=!Number.isNaN(alphaNum)?Math.min(0.72,alphaNum/100):(dark?0.60:0.56);
      tokens['--glass-bg']=toRgba(panel,Math.max(0.42,a-0.08));
      tokens['--glass-bg-strong']=toRgba(panel,Math.min(0.68,a));
      tokens['--glass-bg-subtle']=toRgba(panel,Math.max(0.36,a-0.14));
      const blurNum=typeof tokensObj.glass_blur==='number'?Math.max(0,Math.min(32,tokensObj.glass_blur)):NaN;
      if(!Number.isNaN(blurNum))tokens['--glass-blur']=`${blurNum}px`;
      else root.style.removeProperty('--glass-blur');
      const grad=typeof tokensObj.bg_gradient==='string'?tokensObj.bg_gradient.trim():'';
      if(grad)tokens['--home-bg']=grad;
      else root.style.removeProperty('--home-bg');
      const customVars=(tokensObj.vars&&typeof tokensObj.vars==='object'?tokensObj.vars:{}) as Record<string,unknown>;
      for(const [k,v] of Object.entries(customVars)){
        if(/^--[a-zA-Z0-9_-]{2,48}$/.test(k)&&typeof v==='string')tokens[k]=v;
      }
      const presetId=typeof value.preset==='string'&&value.preset?value.preset:activePresetKey;
      activePresetKey=presetId;
      modeVarCache[`${presetId}:${dark?'dark':'light'}`]=tokens;
      modeVarCache[dark?'dark':'light']=tokens;
      for(const [k,v] of Object.entries(tokens))root.style.setProperty(k,v);
    }catch{
      /* Ignore malformed appearance updates. */
    }
  };
  native.changed.connect(apply);
  reconcileCurrent=()=>native.current(apply);
  native.current(apply);
}
