import os

def fix_frontend_dashboard():
    path = 'd:/python/road-damage-app/frontend/dashboard.html'
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    start_line = -1
    end_line = -1
    
    for i, line in enumerate(lines):
        if 'function renderDetailPanel(c,' in line:
            start_line = i
        if start_line != -1 and 'if (hasAfter) initBASlider();' in line:
            # Check if next line is close brace
            if i+1 < len(lines) and '}' in lines[i+1]:
                end_line = i + 1
                break
                
    if start_line == -1 or end_line == -1:
        print(f"Could not find function bounds: {start_line} to {end_line}")
        return
        
    new_func = """function renderDetailPanel(c, msgs=[]) {
  const BASE = window.location.port === '8443' ? 'https://localhost:8443' : 'http://localhost:8000';
  const hasAfter = afterPhotos[c.complaint_id];
  const dpBody = document.getElementById('dp-body');
  
  let html = '';
  
  // Citizen Box
  if (c.citizen_name) {
    html += `<div class="citizen-info-box">
      <div class="cib-title">👤 Citizen Information</div>
      <div class="cib-row"><span class="label">Name</span><span>${c.citizen_name}</span></div>
      <div class="cib-row"><span class="label">Email</span><span>${c.citizen_email||'—'}</span></div>
      <div class="cib-row"><span class="label">Phone</span><span>${c.citizen_phone||'—'}</span></div>
      <div class="cib-row"><span class="label">Reward Points</span><span style="color:var(--accent)">+10 pts earned</span></div>
    </div>`;
  }

  // Map / Images
  html += `<div class="ba-labels"><span>Before</span><span>${hasAfter?'After (drag slider)':'After repair pending'}</span></div>`;
  if (hasAfter) {
    html += `<div class="ba-wrap" id="ba-wrap">
      <img class="ba-before" src="${BASE}${c.image_url}"/>
      <div class="ba-after-overlay" id="ba-after" style="width:50%"><img src="${hasAfter}" style="width:200%;height:100%;object-fit:cover"/></div>
      <div class="ba-slider" id="ba-slider"><div class="ba-handle">⟺</div></div>
    </div>`;
  } else {
    html += `<img class="dp-img" src="${BASE}${c.image_url}"/>
             <div class="no-after">📸 Upload after-repair photo to enable comparison</div>`;
  }

  if (['in_progress','completed'].includes(c.status)) {
    html += `<button class="upload-after-btn" onclick="triggerAfterPhoto('${c.complaint_id}')">📸 ${hasAfter?'Update':'Upload'} After-Repair Photo</button>`;
  }

  // Info Grid
  html += `<div class="info-grid">
    <div class="info-cell"><div class="info-label">Type</div><div class="info-value">${(c.damage_type||'').replace('_',' ')}</div></div>
    <div class="info-cell"><div class="info-label">Severity</div><div class="info-value"><span class="sev-badge sev-${c.severity}">${(c.severity||'').toUpperCase()}</span></div></div>
    <div class="info-cell"><div class="info-label">AI Confidence</div><div class="info-value">${((c.ai_confidence||0)*100).toFixed(1)}%</div></div>
    <div class="info-cell"><div class="info-label">Area Type</div><div class="info-value" style="color:#f59e0b;font-weight:700">${(c.area_type||'unknown').toUpperCase()}</div></div>
    <div class="info-cell"><div class="info-label">Reports</div><div class="info-value">${c.report_count||1} citizen${(c.report_count||1)>1?'s':''}</div></div>
    <div class="info-cell"><div class="info-label">Reported</div><div class="info-value">${c.created_at ? fmtDate(c.created_at) : '—'}</div></div>
  </div>`;

  // Priority Score
  html += `<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:0.8rem;margin-bottom:0.8rem">
    <div style="font-size:0.72rem;color:var(--muted);text-transform:uppercase;font-weight:700;margin-bottom:0.6rem;display:flex;justify-content:space-between">
      <span>Priority Score Breakdown</span>
      <span style="color:${(c.priority_score||0)>=70?'#ef4444':(c.priority_score||0)>=40?'#f59e0b':'#10b981'};font-size:1rem;font-weight:800">${c.priority_score||0}/100</span>
    </div>`;
  
  const factors = [
    ['Damage Size', c.damage_size_score||0, 45],
    ['Traffic Density', c.traffic_density_score||0, 20],
    ['Accident Risk', c.accident_risk_score||0, 20],
    ['Area Criticality', c.area_criticality_score||0, 20],
  ];
  factors.forEach(([label,val,max]) => {
    html += `<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.35rem">
      <div style="font-size:0.72rem;color:var(--muted);width:100px;flex-shrink:0">${label}</div>
      <div style="flex:1;height:6px;background:var(--bg);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${Math.min(100,val/max*100)}%;background:linear-gradient(90deg,var(--accent2),var(--accent));border-radius:3px"></div>
      </div>
      <div style="font-size:0.72rem;font-weight:700;width:30px;text-align:right;color:var(--text)">${val.toFixed(0)}</div>
    </div>`;
  });
  html += `</div>`;

  // Funds
  html += `<div style="background:var(--card);border:1px solid rgba(16,185,129,0.2);border-radius:10px;padding:0.8rem;margin-bottom:0.8rem">
    <div style="font-size:0.72rem;color:#10b981;text-transform:uppercase;font-weight:700;margin-bottom:0.6rem">Budget Allocation</div>`;
  if (c.allocated_fund > 0) {
    html += `<div style="font-size:1.4rem;font-weight:800;color:#10b981">Rs. ${(c.allocated_fund).toLocaleString()}</div>
             <div style="font-size:0.78rem;color:var(--muted);margin-top:3px">${c.fund_note||''}</div>`;
  } else {
    html += `<div style="font-size:0.82rem;color:var(--muted)">No budget allocated yet</div>`;
  }
  html += `<div style="display:flex;gap:0.4rem;margin-top:0.6rem">
      <input type="number" id="fund-amt-${c.complaint_id}" placeholder="Amount (Rs.)" style="flex:1;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:0.4rem 0.6rem;font-family:inherit;font-size:0.82rem" value="${c.allocated_fund||''}"/>
      <input type="text" id="fund-note-${c.complaint_id}" placeholder="Note" style="flex:1.5;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:0.4rem 0.6rem;font-family:inherit;font-size:0.82rem" value="${c.fund_note||''}"/>
      <button onclick="allocateFund('${c.complaint_id}')" style="background:#10b981;color:#000;border:none;border-radius:6px;padding:0.4rem 0.7rem;font-family:inherit;font-weight:700;font-size:0.78rem;cursor:pointer">Allocate</button>
    </div>
  </div>`;

  // Description & Mini Map
  html += `<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:0.7rem;margin-bottom:0.8rem;font-size:0.8rem;color:var(--muted)">${c.description||''}</div>
  <div style="border-radius:10px;overflow:hidden;margin-bottom:0.8rem;height:130px">
    <div id="dp-mini-map" style="height:130px;border-radius:8px;overflow:hidden"></div>
  </div>`;

  // Status Form
  html += `<div class="status-form">
    <label>Update Status</label>
    <select id="dp-status">
      <option value="pending" ${c.status==='pending'?'selected':''}>Pending</option>
      <option value="assigned" ${c.status==='assigned'?'selected':''}>Assigned</option>
      <option value="in_progress" ${c.status==='in_progress'?'selected':''}>In Progress</option>
      <option value="completed" ${c.status==='completed'?'selected':''}>Completed</option>
      <option value="rejected" ${c.status==='rejected'?'selected':''}>Rejected</option>
    </select>
    <label>Officer Notes</label>
    <textarea id="dp-notes" rows="2" placeholder="Add inspection notes...">${c.officer_notes||''}</textarea>
    <button class="btn-update" onclick="saveStatus('${c.complaint_id}')">Save Update</button>
    <div class="save-success" id="save-success">✓ Updated!</div>
  </div>`;

  // Messages
  html += `<div class="msg-section">
    <div class="msg-title">💬 Message Citizen</div>
    <div class="msg-list" id="msg-list-${c.complaint_id}">`;
  if (msgs.length) {
    msgs.forEach(m => {
      html += `<div class="msg-bubble ${m.sender_role}">
        <div class="msg-meta">${m.sender_name} · ${fmtTime(m.created_at)}</div>
        ${m.message}</div>`;
    });
  } else {
    html += `<div class="no-msg">No messages yet — send an update below</div>`;
  }
  html += `</div>
    <div class="msg-input-row">
      <input class="msg-input" id="msg-input-${c.complaint_id}" placeholder="e.g. Repair scheduled for tomorrow..." onkeydown="if(event.key==='Enter')sendMessage('${c.complaint_id}')"/>
      <button class="msg-send-btn" onclick="sendMessage('${c.complaint_id}')">Send</button>
    </div>
  </div>`;

  dpBody.innerHTML = html;

  // Init map & slider after DOM update
  setTimeout(() => {
    const mel = document.getElementById('dp-mini-map');
    if (mel && window.L) {
      if (mel._lmap) mel._lmap.remove();
      const dm = L.map(mel, {zoomControl:false, attributionControl:false}).setView([c.latitude, c.longitude], 16);
      mel._lmap = dm;
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(dm);
      L.circleMarker([c.latitude, c.longitude], {radius:10, fillColor:'#f5a623', color:'#fff', weight:2, fillOpacity:.9}).addTo(dm);
    }
    if (hasAfter) initBASlider();
  }, 300);
}
"""
    
    # Replace lines from start_line to end_line
    lines[start_line:end_line+1] = [new_func + "\n"]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Successfully fixed frontend/dashboard.html")

if __name__ == "__main__":
    fix_frontend_dashboard()
