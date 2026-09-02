import{p as xt}from"./chunk-JWPE2WC7.DvCuugNx.js";import{bM as gt,ao as $t,au as bt,bP as Ct,ap as wt,bN as vt,d as i,bh as O,bL as Dt,Y as kt,O as Tt,N as U,ar as Q,ac as At,aC as ot}from"../app.BptTHK1i.js";import{p as Bt}from"./cynefin-OW5HDTMX.CITmuvK9.js";import"./framework.BvWD_EvC.js";import"./theme.Do8xN7jn.js";var rt=i(()=>({domains:new Map,transitions:[]}),"createDefaultData"),H=rt(),St=i(()=>H.domains,"getDomains"),Mt=i(()=>H.transitions,"getTransitions"),Lt=i(t=>{if(t)for(const e of t){const n=e.domain,a=(e.items??[]).map(c=>({label:c.label}));H.domains.set(n,{name:n,items:a})}},"setDomains"),zt=i(t=>{t&&(H.transitions=t.filter(e=>e.from===e.to?(O.warn(`Cynefin: self-loop transition on domain "${e.from}" is not meaningful and will be skipped.`),!1):!0).map(e=>({from:e.from,to:e.to,label:e.label||void 0})))},"setTransitions"),Nt=i(()=>U({...At.cynefin,...Q().cynefin}),"getConfig"),Pt=i(()=>{Tt(),H=rt()},"clear"),G={getDomains:St,getTransitions:Mt,setDomains:Lt,setTransitions:zt,getConfig:Nt,clear:Pt,setAccTitle:vt,getAccTitle:wt,setDiagramTitle:Ct,getDiagramTitle:bt,getAccDescription:$t,setAccDescription:gt},It=i(t=>{xt(t,G),G.setDomains(t.domains),G.setTransitions(t.transitions)},"populate"),Wt={parse:i(async t=>{const e=await Bt("cynefin",t);O.debug(e),It(e)},"parse")};function E(t){let e=t+1831565813|0;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}i(E,"seededRandom");function it(t){let e=0;for(let n=0;n<t.length;n++){const a=t.charCodeAt(n);e=(e<<5)-e+a,e|=0}return e}i(it,"hashString");function st(t,e){return typeof t=="number"&&Number.isFinite(t)&&t!==0?t:it(e)}i(st,"resolveSeed");function ct(t,e,n,a){const c=t/2,m=a??t*.015,v=7,W=e/v,d=[];for(let o=0;o<=v;o++){const p=E(n+o*17)*m*2-m;d.push({x:c+p,y:o*W})}let D=`M${d[0].x},${d[0].y}`;for(let o=0;o<d.length-1;o++){const p=d[o],s=d[o+1],f=(p.y+s.y)/2,b=o%2===0?1:-1,h=m*1.5*b*E(n+o*31+7),R=p.x+h,F=f,V=s.x-h;D+=` C${R},${F} ${V},${f} ${s.x},${s.y}`}return D}i(ct,"generateFoldPath");function lt(t,e,n,a){const c=e/2,m=a??e*.015,v=7,W=t/v,d=[];for(let o=0;o<=v;o++){const p=E(n+o*23)*m*2-m;d.push({x:o*W,y:c+p})}let D=`M${d[0].x},${d[0].y}`;for(let o=0;o<d.length-1;o++){const p=d[o],s=d[o+1],f=(p.x+s.x)/2,b=o%2===0?1:-1,h=m*1.5*b*E(n+o*37+11),R=f,F=p.y+h,V=f,L=s.y-h;D+=` C${R},${F} ${V},${L} ${s.x},${s.y}`}return D}i(lt,"generateHorizontalBoundary");function dt(t,e){const n=t/2,a=e*.5,c=e,m=t*.03;return[`M${n},${a}`,`C${n+m},${a+(c-a)*.2}`,`${n-m*1.5},${a+(c-a)*.55}`,`${n+m*.5},${a+(c-a)*.75}`,`C${n-m},${a+(c-a)*.85}`,`${n+m*.3},${a+(c-a)*.95}`,`${n},${c}`].join(" ")}i(dt,"generateCliffPath");function ft(t,e,n,a){return[`M${t-n},${e}`,`A${n},${a} 0 1,1 ${t+n},${e}`,`A${n},${a} 0 1,1 ${t-n},${e}`,"Z"].join(" ")}i(ft,"generateConfusionPath");var at={complex:{model:"Probe → Sense → Respond",practice:"Emergent Practices"},complicated:{model:"Sense → Analyse → Respond",practice:"Good Practices"},clear:{model:"Sense → Categorise → Respond",practice:"Best Practices"},chaotic:{model:"Act → Sense → Respond",practice:"Novel Practices"},confusion:{model:"",practice:"Disorder"}},Rt=i((t,e)=>{const n=t/2,a=e/2;return{complex:{cx:n/2,cy:a/2,x:0,y:0,w:n,h:a},complicated:{cx:n+n/2,cy:a/2,x:n,y:0,w:n,h:a},chaotic:{cx:n/2,cy:a+a/2,x:0,y:a,w:n,h:a},clear:{cx:n+n/2,cy:a+a/2,x:n,y:a,w:n,h:a},confusion:{cx:n,cy:a,x:n*.7,y:a*.7,w:n*.6,h:a*.6}}},"getDomainLayouts"),Ft=i(()=>{const t=ot(),e=Q();return U(t,e.themeVariables).cynefin},"getCynefinDomainColors"),q=3,Vt=i((t,e,n,a)=>{const c=a.db,m=c.getDomains(),v=c.getTransitions(),W=c.getDiagramTitle(),d=c.getAccTitle(),D=c.getAccDescription(),o=c.getConfig(),p=Ft();O.debug("Rendering Cynefin diagram");const s=o.width,f=o.height,b=o.padding,h=o.showDomainDescriptions,R=o.boundaryAmplitude,F=s+b*2,V=f+b*2,L={complex:p.complexBg,complicated:p.complicatedBg,clear:p.clearBg,chaotic:p.chaoticBg,confusion:p.confusionBg},k=Dt(e);kt(k,V,F,o.useMaxWidth??!0),k.attr("viewBox",`0 0 ${F} ${V}`),d&&k.append("title").text(d),D&&k.append("desc").text(D);const T=k.append("g").attr("transform",`translate(${b}, ${b})`),_=Rt(s,f),Z=st(o.seed,e),mt=T.append("g").attr("class","cynefin-backgrounds"),X=["complex","complicated","chaotic","clear"];for(const l of X){const r=_[l];mt.append("rect").attr("class","cynefinDomain").attr("x",r.x).attr("y",r.y).attr("width",r.w).attr("height",r.h).attr("fill",L[l]).attr("fill-opacity",.4).attr("stroke","none")}const j=T.append("g").attr("class","cynefin-boundaries");j.append("path").attr("class","cynefinBoundary").attr("d",ct(s,f,Z,R)).attr("fill","none"),j.append("path").attr("class","cynefinBoundary").attr("d",lt(s,f,Z+100,R)).attr("fill","none"),j.append("path").attr("class","cynefinCliff").attr("d",dt(s,f)).attr("fill","none");const pt=s*.15,yt=f*.15;T.append("path").attr("class","cynefinConfusion").attr("d",ft(s/2,f/2,pt,yt)).attr("fill",L.confusion).attr("fill-opacity",.5);const J=T.append("g").attr("class","cynefin-labels");for(const l of X){const r=_[l];J.append("text").attr("class","cynefinDomainLabel").attr("x",r.cx).attr("y",h?r.cy-30:r.cy).attr("text-anchor","middle").attr("dominant-baseline","middle").text(l.charAt(0).toUpperCase()+l.slice(1))}if(J.append("text").attr("class","cynefinDomainLabel").attr("x",s/2).attr("y",h?f/2-10:f/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text("Confusion"),h){const l=T.append("g").attr("class","cynefin-subtitles");for(const r of X){const u=_[r],y=at[r];l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy-10).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.model),l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy+5).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.practice)}l.append("text").attr("class","cynefinSubtitle").attr("x",s/2).attr("y",f/2+8).attr("text-anchor","middle").attr("dominant-baseline","middle").text(at.confusion.practice)}const K=T.append("g").attr("class","cynefin-items"),A=26,tt=10,ut=["complex","complicated","chaotic","clear","confusion"];for(const l of ut){const r=m.get(l);if(!r||r.items.length===0)continue;const u=_[l],y=l==="confusion";let z=r.items,N=0;y&&r.items.length>q&&(N=r.items.length-q,z=r.items.slice(0,q));let B;if(y){const g=h?22:14;B=u.cy+g}else B=u.cy+(h?25:15);if([...z].forEach((g,S)=>{const C=B+S*(A+4),M=K.append("g"),P=M.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",A/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(g.label);let $=g.label.length*7;const x=P.node();if(x&&typeof x.getBBox=="function"){const Y=x.getBBox();Y.width>0&&($=Y.width)}const w=$+tt*2,I=u.cx-w/2;M.attr("transform",`translate(${I}, ${C})`),M.insert("rect","text").attr("class","cynefinItem").attr("x",0).attr("y",0).attr("width",w).attr("height",A).attr("rx",4).attr("ry",4).attr("fill",L[l]).attr("fill-opacity",.95),P.attr("x",w/2).attr("y",A/2)}),N>0){const g=B+z.length*(A+4),S=`+${N} more`,C=K.append("g"),M=C.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",A/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(S);let P=S.length*7;const $=M.node();if($&&typeof $.getBBox=="function"){const I=$.getBBox();I.width>0&&(P=I.width)}const x=P+tt*2,w=u.cx-x/2;C.attr("transform",`translate(${w}, ${g})`),C.insert("rect","text").attr("class","cynefinItemOverflow").attr("x",0).attr("y",0).attr("width",x).attr("height",A).attr("rx",4).attr("ry",4).attr("fill",L[l]).attr("fill-opacity",.6),M.attr("x",x/2).attr("y",A/2)}}if(v.length>0){const l=k.select("defs").empty()?k.append("defs"):k.select("defs"),r=`cynefin-arrow-${e}`;l.append("marker").attr("id",r).attr("viewBox","0 0 10 10").attr("refX",9).attr("refY",5).attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto-start-reverse").append("path").attr("d","M 0 0 L 10 5 L 0 10 z").attr("class","cynefinArrowHead");const u=T.append("g").attr("class","cynefin-arrows");v.forEach(y=>{const z=_[y.from],N=_[y.to];if(!z||!N)return;if(y.from===y.to){O.warn(`Cynefin renderer: skipping self-loop on domain "${y.from}"`);return}const B=z.cx,g=z.cy,S=N.cx,C=N.cy,M=(B+S)/2,P=(g+C)/2,$=S-B,x=C-g,w=Math.sqrt($*$+x*x),I=w*.15,Y=-x/w,ht=$/w,et=M+Y*I,nt=P+ht*I;u.append("path").attr("class","cynefinArrowLine").attr("d",`M${B},${g} Q${et},${nt} ${S},${C}`).attr("fill","none").attr("marker-end",`url(#${r})`),y.label&&u.append("text").attr("class","cynefinArrowLabel").attr("x",et).attr("y",nt-6).attr("text-anchor","middle").attr("dominant-baseline","auto").text(y.label)})}W&&T.append("text").attr("class","cynefinTitle").attr("x",s/2).attr("y",-b/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text(W)},"draw"),_t={draw:Vt},Et=i(()=>{const t=ot(),e=Q();return U(t,e.themeVariables).cynefin},"getCynefinTheme"),Ht=i(()=>{const t=Et();return`
	.cynefinDomain {
		stroke: none;
	}
	.cynefinDomainLabel {
		font-size: ${t.domainFontSize}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	.cynefinSubtitle {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
		font-style: italic;
	}
	.cynefinItem {
		fill-opacity: 0.95;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
	}
	.cynefinItemText {
		font-size: ${t.itemFontSize}px;
		fill: ${t.textColor};
	}
	.cynefinItemOverflow {
		fill-opacity: 0.6;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
		stroke-dasharray: 3 2;
	}
	.cynefinBoundary {
		stroke: ${t.boundaryColor};
		stroke-width: ${t.boundaryWidth};
		stroke-dasharray: 6 3;
	}
	.cynefinCliff {
		stroke: ${t.cliffColor};
		stroke-width: ${t.cliffWidth};
	}
	.cynefinConfusion {
		stroke: ${t.boundaryColor};
		stroke-width: 1.5;
		stroke-dasharray: 4 2;
	}
	.cynefinArrowLine {
		stroke: ${t.arrowColor};
		stroke-width: ${t.arrowWidth};
		fill: none;
	}
	.cynefinArrowHead {
		fill: ${t.arrowColor};
		stroke: none;
	}
	.cynefinArrowLabel {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
	}
	.cynefinTitle {
		font-size: ${t.domainFontSize+2}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	`},"styles"),Yt=Ht,Ut={parser:Wt,db:G,renderer:_t,styles:Yt};export{Ut as diagram};
