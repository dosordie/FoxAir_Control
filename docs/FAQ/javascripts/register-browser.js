/* Durchsuchbare, rein lesende FoxAir-Registerreferenz (ohne externe Bibliotheken). */
(function () {
  "use strict";
  var root = document.getElementById("fox-register-browser");
  if (!root) return;
  var PER_PAGE = 60;
  var collator = new Intl.Collator("de", {numeric: true, sensitivity: "base"});
  var s = {all:[], shown:[], query:"", category:"all", block:"all", access:"all",
    sort:"id", desc:false, page:0, selected:null};

  function esc(x) {
    return String(x == null ? "" : x).replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }
  function pretty(x) {
    if (x == null) return "";
    if (Array.isArray(x)) return x.map(pretty).join(", ");
    if (typeof x === "object") return Object.entries(x).map(function (e) {
      return e[0] + ": " + pretty(e[1]);
    }).join("; ");
    return String(x);
  }
  function normal(x) {
    return String(x).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  }
  function catLabel(x) {
    return x==="main" ? "Mainboard" : x==="display" ? "Display" : "Virtuell";
  }
  function attr(label,val) {
    if (val == null || val === "") return "";
    return '<div class="fox-rb-fact"><dt>'+esc(label)+'</dt><dd>'+esc(pretty(val))+'</dd></div>';
  }
  function mapping(title,data) {
    if (!data || typeof data!=="object" || Array.isArray(data)) return "";
    var entries=Object.entries(data).sort(function(a,b){return collator.compare(a[0],b[0]);});
    if (!entries.length) return "";
    return '<h3>'+esc(title)+'</h3><dl class="fox-rb-values">'+entries.map(function(e){
      return '<dt>'+esc(e[0])+'</dt><dd>'+esc(pretty(e[1]))+'</dd>';
    }).join("")+'</dl>';
  }
  function makeDetail(r) {
    var k=r.knowledge||{};
    var link=new URL(window.location.href);
    link.searchParams.set("r",String(r.id));
    var note=r.notes||r.note;
    var extras=[
      attr("Typ",r.type),attr("Modbus-Funktion",r.function),attr("Einheit",r.unit),
      attr("Firmware",r.firmware),attr("Parametergruppe",r.block||r.group),
      attr("Schnittstelle",r.interface),attr("Rohwertformat",r.raw_format),
      attr("Speicherung",r.persistence),attr("Quell-Slave",r.source_slave),
      attr("Quellregister",r.source_register),attr("Mainboard-Bezüge",r.main_aliases)
    ].join("");
    return '<tr class="fox-rb-detailrow"><td colspan="5"><div class="fox-rb-detail">'+
      (r.category==="virtual" ? '<p class="fox-rb-alert"><strong>Virtuelle FoxAir-ID:</strong> '+ 
       'nicht direkt über Modbus adressierbar. Die Quelle ist gesondert angegeben.</p>' : "")+
      (r.description ? '<strong>Beschreibung</strong><p>'+esc(r.description)+'</p>' : "")+
      (note ? '<strong>Hinweise</strong><p>'+esc(pretty(note))+'</p>' : "")+
      mapping("Werte und Bedeutung",r.value_map)+
      mapping("Bit-Belegung",r.bit_map)+
      mapping("Bit-Erklärungen",r.bit_descriptions)+
      (extras ? '<dl class="fox-rb-facts">'+extras+'</dl>' : "")+
      (Object.keys(k).length ? '<section class="fox-rb-knowledge"><h3>Ergänzendes Wissen</h3>'+
        (k.description ? '<p>'+esc(pretty(k.description))+'</p>' : "")+
        (k.knowledge ? '<p>'+esc(pretty(k.knowledge))+'</p>' : "")+
        (k.notes||k.note ? '<p>'+esc(pretty(k.notes||k.note))+'</p>' : "")+
        (k.range!=null ? '<p><strong>Wertebereich:</strong> '+esc(pretty(k.range))+'</p>' : "")+
        (k.default!=null ? '<p><strong>Standardwert:</strong> '+esc(pretty(k.default))+'</p>' : "")+
        '</section>' : "")+
      '<div class="fox-rb-actions"><a href="'+esc(link.toString())+'">Direktlink zu Register '+esc(r.id)+
      '</a><button type="button" data-copy="'+esc(r.id)+'">Link kopieren</button></div>'+
      '</div></td></tr>';
  }
  function row(r) {
    var open=s.selected===r.id;
    return '<tr>'+
      '<td class="fox-rb-number">'+esc(r.id)+'</td>'+
      '<td>'+esc(r.code||"–")+'</td>'+
      '<td><button class="fox-rb-open" type="button" data-open="'+esc(r.id)+
      '" aria-expanded="'+(open?"true":"false")+'">'+
      esc(r.name||"Unbekanntes Register")+' <span aria-hidden="true">'+(open?"▴":"▾")+'</span></button></td>'+
      '<td><span class="fox-rb-pill '+(r.category==="virtual"?"fox-rb-pill-virtual":"")+'">'+
      esc(catLabel(r.category))+'</span>'+
      (r.block?'<span class="fox-rb-block">'+esc(r.block)+'</span>':"")+'</td>'+
      '<td class="fox-rb-access">'+esc(r.access)+'</td></tr>'+
      (open?makeDetail(r):"");
  }
  function render() {
    var pages=Math.max(1,Math.ceil(s.shown.length/PER_PAGE));
    s.page=Math.min(s.page,pages-1);
    var rows=s.shown.slice(s.page*PER_PAGE,(s.page+1)*PER_PAGE);
    root.querySelector("#fox-rb-body").innerHTML=rows.length?rows.map(row).join(""):
      '<tr><td colspan="5" class="fox-rb-empty">Keine Register gefunden. Bitte Suche oder Filter anpassen.</td></tr>';
    root.querySelector("#fox-rb-count").textContent=
      s.shown.length.toLocaleString("de-DE")+" von "+s.all.length.toLocaleString("de-DE")+" Registern";
    root.querySelector("#fox-rb-page").textContent="Seite "+(s.page+1)+" / "+pages;
    root.querySelector("#fox-rb-prev").disabled=s.page===0;
    root.querySelector("#fox-rb-next").disabled=s.page===pages-1;
    root.querySelectorAll("[data-sort]").forEach(function(b){
      var active=b.dataset.sort===s.sort;
      b.setAttribute("aria-pressed",active?"true":"false");
      b.querySelector("span").textContent=active?(s.desc?" ↓":" ↑"):"";
    });
  }
  function filter() {
    var terms=normal(s.query).split(/\s+/).filter(Boolean);
    s.shown=s.all.filter(function(r){
      if(s.category!=="all"&&r.category!==s.category)return false;
      if(s.block!=="all"&&String(r.block||r.group||"")!==s.block)return false;
      if(s.access==="read"&&r.access!=="Nur lesen")return false;
      if(s.access==="write"&&!["Lesen / Schreiben","Schreiben"].includes(r.access))return false;
      return terms.every(function(t){return r._search.includes(t);});
    });
    s.shown.sort(function(a,b){
      var result=s.sort==="id"?a.id-b.id||collator.compare(a.category,b.category):
        collator.compare(String(a[s.sort]||""),String(b[s.sort]||""));
      return s.desc?-result:result;
    });
    render();
  }
  function init(data) {
    if(data.schema!==1||!Array.isArray(data.registers))throw Error("Unbekanntes Datenformat");
    s.all=data.registers;
    s.all.forEach(function(r){
      r._search=normal([r.id,r.name,r.code,r.block,r.group,r.type,r.description,
        r.notes,r.note,r.unit,r.firmware,r.app_label,r.access,r.value_map,
        r.bit_map,r.bit_descriptions,r.knowledge,catLabel(r.category)].map(pretty).join(" "));
    });
    root.innerHTML=
      '<div class="fox-rb-toolbar">'+
       '<label for="fox-rb-search">Register suchen</label>'+
       '<input type="search" id="fox-rb-search" autocomplete="off" placeholder="2057, H40, Abtauen, SG Ready ...">'+
       '<div class="fox-rb-filters">'+
        '<label>Bereich<select id="fox-rb-category"><option value="all">Alle Bereiche</option><option value="main">Mainboard</option><option value="display">Display</option><option value="virtual">Virtuell</option></select></label>'+
        '<label>Gruppe<select id="fox-rb-block"><option value="all">Alle Gruppen</option></select></label>'+
        '<label>Zugriff<select id="fox-rb-access"><option value="all">Alle</option><option value="read">Nur lesen</option><option value="write">Schreibbar</option></select></label>'+
        '<button type="button" id="fox-rb-reset">Zurücksetzen</button>'+
       '</div></div>'+
      '<div class="fox-rb-summary"><strong id="fox-rb-count" role="status" aria-live="polite"></strong>'+
       '<span class="fox-rb-muted">Bezeichnung anklicken für Details</span></div>'+
      '<div class="fox-rb-scroll"><table class="fox-rb-table"><thead><tr>'+
       '<th><button type="button" data-sort="id">Register<span></span></button></th>'+
       '<th><button type="button" data-sort="code">Code<span></span></button></th>'+
       '<th><button type="button" data-sort="name">Bezeichnung<span></span></button></th>'+
       '<th><button type="button" data-sort="block">Bereich / Gruppe<span></span></button></th>'+
       '<th><button type="button" data-sort="access">Zugriff<span></span></button></th>'+
      '</tr></thead><tbody id="fox-rb-body"></tbody></table></div>'+
      '<div class="fox-rb-pager"><button type="button" id="fox-rb-prev">← Zurück</button>'+
       '<span id="fox-rb-page"></span><button type="button" id="fox-rb-next">Weiter →</button></div>';
    var b=root.querySelector("#fox-rb-block");
    Array.from(new Set(s.all.map(function(r){return String(r.block||r.group||"");}).filter(Boolean)))
      .sort(collator.compare).forEach(function(name){
        var opt=document.createElement("option");opt.value=name;opt.textContent=name;b.appendChild(opt);
      });
    var selected=new URLSearchParams(window.location.search).get("r");
    if(selected&&/^\d+$/.test(selected)&&s.all.some(function(r){return r.id===Number(selected);})) {
      s.query=selected;s.selected=Number(selected);
      root.querySelector("#fox-rb-search").value=selected;
    }
    root.querySelector("#fox-rb-search").addEventListener("input",function(e){
      s.query=e.target.value;s.page=0;s.selected=null;filter();
    });
    ["category","block","access"].forEach(function(field){
      root.querySelector("#fox-rb-"+field).addEventListener("change",function(e){
        s[field]=e.target.value;s.page=0;s.selected=null;filter();
      });
    });
    root.querySelector("#fox-rb-reset").addEventListener("click",function(){
      s.query="";s.category="all";s.block="all";s.access="all";s.page=0;
      s.selected=null;s.sort="id";s.desc=false;
      root.querySelector("#fox-rb-search").value="";
      ["category","block","access"].forEach(function(k){root.querySelector("#fox-rb-"+k).value="all";});
      filter();
    });
    root.querySelector("#fox-rb-prev").addEventListener("click",function(){if(s.page>0){s.page--;render();}});
    root.querySelector("#fox-rb-next").addEventListener("click",function(){
      if((s.page+1)*PER_PAGE<s.shown.length){s.page++;render();}
    });
    root.addEventListener("click",function(e){
      var sort=e.target.closest("[data-sort]");
      if(sort){
        var field=sort.dataset.sort;
        s.desc=s.sort===field?!s.desc:false;s.sort=field;s.page=0;s.selected=null;filter();return;
      }
      var open=e.target.closest("[data-open]");
      if(open){var id=Number(open.dataset.open);s.selected=s.selected===id?null:id;render();return;}
      var copy=e.target.closest("[data-copy]");
      if(copy){
        var link=new URL(window.location.href);link.searchParams.set("r",copy.dataset.copy);
        if(navigator.clipboard&&navigator.clipboard.writeText){
          navigator.clipboard.writeText(link.toString()).then(function(){copy.textContent="Kopiert ✓";})
            .catch(function(){copy.textContent="Direktlink links öffnen";});
        }else{copy.textContent="Direktlink links öffnen";}
      }
    });
    filter();
  }
  fetch(root.getAttribute("data-src"),{credentials:"same-origin"})
    .then(function(res){if(!res.ok)throw Error("HTTP "+res.status);return res.json();})
    .then(init)
    .catch(function(e){
      root.innerHTML='<p class="fox-rb-alert">Die Registerliste konnte nicht geladen werden ('+
        esc(e.message)+'). Bitte die Seite neu laden oder den Website-Build prüfen.</p>';
    });
})();
