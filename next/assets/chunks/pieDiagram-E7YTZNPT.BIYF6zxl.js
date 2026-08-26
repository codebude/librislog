import{p as rt}from"./chunk-JWPE2WC7.DCiN5Ds-.js";import{$ as b,c0 as G,j as nt,ao as it,bM as ot,ap as st,bN as lt,au as ct,bP as ut,d,bh as B,as as gt,N as dt,bL as pt,bt as ht,Y as ft,O as mt,ac as vt}from"../app.M2-KfjbJ.js";import{p as xt}from"./cynefin-OW5HDTMX.CITmuvK9.js";import{d as q}from"./arc.Byq7RQUQ.js";import{o as St}from"./ordinal.BYWQX77i.js";import"./framework.BvWD_EvC.js";import"./theme.2oPJDPwH.js";import"./init.Gi6I4Gst.js";function yt(t,n){return n<t?-1:n>t?1:n>=t?0:NaN}function wt(t){return t}function At(){var t=wt,n=yt,y=null,T=b(0),l=b(G),p=b(0);function i(e){var r,s=(e=nt(e)).length,h,w,C=0,f=new Array(s),o=new Array(s),D=+T.apply(this,arguments),z=Math.min(G,Math.max(-G,l.apply(this,arguments)-D)),k,N=Math.min(Math.abs(z)/s,p.apply(this,arguments)),u=N*(z<0?-1:1),A;for(r=0;r<s;++r)(A=o[f[r]=r]=+t(e[r],r,e))>0&&(C+=A);for(n!=null?f.sort(function(E,m){return n(o[E],o[m])}):y!=null&&f.sort(function(E,m){return y(e[E],e[m])}),r=0,w=C?(z-s*u)/C:0;r<s;++r,D=k)h=f[r],A=o[h],k=D+(A>0?A*w:0)+u,o[h]={data:e[h],index:r,value:A,startAngle:D,endAngle:k,padAngle:N};return o}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:b(+e),i):t},i.sortValues=function(e){return arguments.length?(n=e,y=null,i):n},i.sort=function(e){return arguments.length?(y=e,n=null,i):y},i.startAngle=function(e){return arguments.length?(T=typeof e=="function"?e:b(+e),i):T},i.endAngle=function(e){return arguments.length?(l=typeof e=="function"?e:b(+e),i):l},i.padAngle=function(e){return arguments.length?(p=typeof e=="function"?e:b(+e),i):p},i}var $t=vt.pie,I={sections:new Map,showData:!1},P=I.sections,V=I.showData,Ct=structuredClone($t),Dt=d(()=>structuredClone(Ct),"getConfig"),bt=d(()=>{P=new Map,V=I.showData,mt()},"clear"),Tt=d(({label:t,value:n})=>{if(n<0)throw new Error(`"${t}" has invalid value: ${n}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);P.has(t)||(P.set(t,n),B.debug(`added new section: ${t}, with value: ${n}`))},"addSection"),kt=d(()=>P,"getSections"),Mt=d(t=>{V=t},"setShowData"),zt=d(()=>V,"getShowData"),J={getConfig:Dt,clear:bt,setDiagramTitle:ut,getDiagramTitle:ct,setAccTitle:lt,getAccTitle:st,setAccDescription:ot,getAccDescription:it,addSection:Tt,getSections:kt,setShowData:Mt,getShowData:zt},Et=d((t,n)=>{rt(t,n),n.setShowData(t.showData),t.sections.map(n.addSection)},"populateDb"),Lt={parse:d(async t=>{const n=await xt("pie",t);B.debug(n),Et(n,J)},"parse")},Nt=d(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),Rt=Nt,Ot=d(t=>{const n=[...t.values()].reduce((l,p)=>l+p,0),y=[...t.entries()].map(([l,p])=>({label:l,value:p})).filter(l=>l.value/n*100>=1);return At().value(l=>l.value).sort(null)(y)},"createPieArcs"),Pt=d((t,n,y,T)=>{var Z;B.debug(`rendering pie chart
`+t);const l=T.db,p=gt(),i=dt(l.getConfig(),p.pie),e=40,r=18,s=4,h=450,w=h,C=pt(n),f=C.append("g");f.attr("transform","translate("+w/2+","+h/2+")");const{themeVariables:o}=p;let[D]=ht(o.pieOuterStrokeWidth);D??(D=2);const z=i.legendPosition,k=i.textPosition,N=i.donutHole>0&&i.donutHole<=.9?i.donutHole:0,u=Math.min(w,h)/2-e,A=q().innerRadius(N*u).outerRadius(u),E=q().innerRadius(u*k).outerRadius(u*k),m=f.append("g");m.append("circle").attr("cx",0).attr("cy",0).attr("r",u+D/2).attr("class","pieOuterCircle");const R=l.getSections(),K=Ot(R),Q=[o.pie1,o.pie2,o.pie3,o.pie4,o.pie5,o.pie6,o.pie7,o.pie8,o.pie9,o.pie10,o.pie11,o.pie12];let W=0;R.forEach(a=>{W+=a});const j=K.filter(a=>(a.data.value/W*100).toFixed(0)!=="0"),F=St(Q).domain([...R.keys()]);m.selectAll("mySlices").data(j).enter().append("path").attr("d",A).attr("fill",a=>F(a.data.label)).attr("class",a=>{let c="pieCircle";return i.highlightSlice==="hover"?c+=" highlightedOnHover":i.highlightSlice===a.data.label&&(c+=" highlighted"),c}),m.selectAll("mySlices").data(j).enter().append("text").text(a=>(a.data.value/W*100).toFixed(0)+"%").attr("transform",a=>"translate("+E.centroid(a)+")").style("text-anchor","middle").attr("class","slice");const tt=f.append("text").text(l.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText"),L=[...R.entries()].map(([a,c])=>({label:a,value:c})),$=f.selectAll(".legend").data(L).enter().append("g").attr("class","legend");$.append("rect").attr("width",r).attr("height",r).style("fill",a=>F(a.label)).style("stroke",a=>F(a.label)),$.append("text").attr("x",r+s).attr("y",r-s).text(a=>l.getShowData()?`${a.label} [${a.value}]`:a.label);const M=Math.max(...$.selectAll("text").nodes().map(a=>(a==null?void 0:a.getBoundingClientRect().width)??0));let O=h,H=w+e;const g=r+s,_=L.length*g;switch(z){case"center":$.attr("transform",(a,c)=>{const v=g*L.length/2,x=-M/2-(r+s),S=c*g-v;return"translate("+x+","+S+")"});break;case"top":O+=_,$.attr("transform",(a,c)=>{const v=u,x=-M/2-(r+s),S=c*g-v;return`translate(${x}, ${S})`}),m.attr("transform",()=>`translate(0, ${_+g})`);break;case"bottom":O+=_,$.attr("transform",(a,c)=>{const v=-u-g,x=-M/2-(r+s),S=c*g-v;return"translate("+x+","+S+")"});break;case"left":H+=r+s+M,$.attr("transform",(a,c)=>{const v=g*L.length/2,x=-u-(r+s),S=c*g-v;return"translate("+x+","+S+")"}),m.attr("transform",()=>`translate(${M+r+s}, 0)`);break;case"right":default:H+=r+s+M,$.attr("transform",(a,c)=>{const v=g*L.length/2,x=12*r,S=c*g-v;return"translate("+x+","+S+")"});break}const U=((Z=tt.node())==null?void 0:Z.getBoundingClientRect().width)??0,et=w/2-U/2,at=w/2+U/2,X=Math.min(0,et),Y=Math.max(H,at)-X;C.attr("viewBox",`${X} 0 ${Y} ${O}`),ft(C,O,Y,i.useMaxWidth)},"draw"),Wt={draw:Pt},Xt={parser:Lt,db:J,renderer:Wt,styles:Rt};export{Xt as diagram};
