/**
 * S1VAVE & Roland S-1 Unified Controller & Monitor
 * Hardware Control Surface, Patch Manager, Real-time VU Levels, Oscilloscope & MIDI Monitor
 * (c) 2026 S1Vave Project / GPL-3.0
 */

// --- Global State ---
const state = {
  midiAccess: null,
  midiInputs: [],
  midiOutputs: [],
  s1Out: null,
  fm1Out: null,
  s1In: null,
  fm1In: null,
  midiIn: null,
  allMidiIn: true,
  activeTarget: 'both', // 'both', 's1', 'fm1'
  paramLink: true,      // Keep both synths synchronized unless individually targeted
  octave: 4,            // Octave 4 (C4 = 60)
  velocity: 100,
  isLatched: false,
  latchedNotes: new Set(),
  activeNotes: new Map(), // note -> velocity / start time
  seqInterval: null,
  seqStep: 0,
  currentPreset: 0,     // 0..98 (0-indexed, P01 to P99)
  
  // Audio Monitoring & Metering
  micActive: false,
  audioContext: null,
  analyserNode: null,
  micStream: null,
  vuLevels: {
    s1L: 0, s1R: 0, s1PeakL: 0, s1PeakR: 0,
    fm1L: 0, fm1R: 0, fm1PeakL: 0, fm1PeakR: 0
  },
  synthSimLevel: 0,
  synthPhase: 0,
  
  // MIDI Traffic Log
  midiFilter: 'all', // 'all', 'note', 'cc'
  midiLogCount: 0,

  // Arpeggiator & Matrix state
  arp: {
    on: false,
    hold: false,
    type: 0,
    rate: 2,
    tempo: 120,
    pri: 0
  },
  drawSteps: new Array(16).fill(0),
  chopMask: new Array(16).fill(true),

  // Comprehensive parameter cache (Full 59 Roland S-1 & S1Vave parameters)
  params: {
    14: 3,    // OSC Range (0=64', 1=32', 2=16', 3=8', 4=4', 5=2')
    20: 127,  // Saw Level
    19: 0,    // Pulse/Square Level
    15: 0,    // Pulse Width / PWM Depth
    16: 1,    // PWM Source (0=ENV, 1=MAN, 2=LFO)
    21: 0,    // Sub Osc Level
    22: 2,    // Sub Type (0=-2o.A, 1=-2oc, 2=-1oc)
    23: 0,    // Noise Level
    78: 0,    // Noise Mode (0=Pink, 1=White)
    76: 64,   // Fine Tune (-64..+63)
    18: 2,    // OSC Bend Sensitivity (0..24 ST)
    107: 0,   // OSC Draw Switch (0=OFF, 1=STEP, 2=SLOPE)
    102: 0,   // OSC Draw Multiply (0..31 -> 1.0x..32.0x)
    103: 0,   // OSC Chop Overtone (0..200, >100 rev phase)
    104: 0,   // OSC Chop Comb (0..31 -> 1.0x..32.0x)
    108: 0,   // Filter Color (0=S-1 Clean, 1=Midnight Warm)
    109: 64,  // Tone Tilt (64 = Flat)
    110: 64,  // Warmth & Bass Retention (50%)
    74: 127,  // Filter Cutoff (open)
    71: 0,    // Filter Resonance
    24: 0,    // Filter Env Depth
    25: 0,    // Filter LFO Depth
    26: 64,   // Filter Keyboard Track
    27: 2,    // Filter Bend Sensitivity
    73: 0,    // Attack
    75: 64,   // Decay
    30: 127,  // Sustain
    72: 30,   // Release
    28: 1,    // Amp Mode (0=GATE, 1=ENV)
    29: 2,    // Env Trigger (0=LFO, 1=GATE, 2=GATE+TRIG)
    12: 2,    // LFO Wave (0=SAW, 1=ISW, 2=TRI, 3=SQR, 4=RND, 5=NOI)
    3: 60,    // LFO Rate
    13: 0,    // Pitch LFO Depth
    1: 15,    // Mod Depth
    79: 0,    // LFO Mode (0=NORM, 1=FAST)
    106: 0,   // LFO Sync (0=OFF, 1=ON)
    105: 0,   // LFO Key Trigger (0=OFF, 1=ON)
    32: 0,    // Riser Mode (0=OFF, 1=SYNC, 2=QUIV, 3=QV.PAN)
    33: 30,   // Riser Resonance (0..100)
    34: 0,    // Riser Shape (0..100)
    35: 80,   // Riser Level (0..100)
    93: 0,    // Chorus Type (0=OFF, 1..4)
    92: 0,    // Delay Level
    90: 50,   // Delay Time
    36: 50,   // Delay Feedback
    37: 1,    // Delay Tempo Sync (0=OFF, 1=ON)
    91: 0,    // Reverb Level
    89: 100,  // Reverb Time
    38: 5,    // Reverb Type (0=AMB..5=SPRING..6=MOD)
    39: 20,   // Reverb Pre-Delay (0..100ms)
    80: 0,    // Poly Mode (0=MONO, 1=UNISON 8V, 2=POLY 8V, 3=CHORD)
    31: 0,    // Portamento Mode (0=OFF, 1=ON, 2=AUTO)
    65: 0,    // Portamento Switch (0=OFF, 1=ON)
    64: 0,    // Sustain Pedal (0=OFF, 127=HOLD)
    5: 30,    // Portamento Time
    77: 60,   // Key Transpose (-60..+60 ST)
    7: 90,    // Patch Volume
    81: 1,    // Chord Voice 2 SW (0=OFF, 1=ON)
    85: 12,   // Chord Voice 2 Shift (-12..+12 ST)
    82: 1,    // Chord Voice 3 SW (0=OFF, 1=ON)
    86: 12,   // Chord Voice 3 Shift (-12..+12 ST)
    83: 1,    // Chord Voice 4 SW (0=OFF, 1=ON)
    87: 12    // Chord Voice 4 Shift (-12..+12 ST)
  }
};

// --- Note Definition Table for 25-key Keyboard ---
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const KEY_DEFS = [
  // Octave 1 (C to B): semitones 0 to 11 (Z-row)
  { name: 'C',  semi: 0,  isBlack: false, keyChar: 'Z' },
  { name: 'C#', semi: 1,  isBlack: true,  keyChar: 'S' },
  { name: 'D',  semi: 2,  isBlack: false, keyChar: 'X' },
  { name: 'D#', semi: 3,  isBlack: true,  keyChar: 'D' },
  { name: 'E',  semi: 4,  isBlack: false, keyChar: 'C' },
  { name: 'F',  semi: 5,  isBlack: false, keyChar: 'V' },
  { name: 'F#', semi: 6,  isBlack: true,  keyChar: 'G' },
  { name: 'G',  semi: 7,  isBlack: false, keyChar: 'B' },
  { name: 'G#', semi: 8,  isBlack: true,  keyChar: 'H' },
  { name: 'A',  semi: 9,  isBlack: false, keyChar: 'N' },
  { name: 'A#', semi: 10, isBlack: true,  keyChar: 'J' },
  { name: 'B',  semi: 11, isBlack: false, keyChar: 'M' },

  // Octave 2 (C to C): semitones 12 to 24 (Q-row)
  { name: 'C',  semi: 12, isBlack: false, keyChar: 'Q' },
  { name: 'C#', semi: 13, isBlack: true,  keyChar: '2' },
  { name: 'D',  semi: 14, isBlack: false, keyChar: 'W' },
  { name: 'D#', semi: 15, isBlack: true,  keyChar: '3' },
  { name: 'E',  semi: 16, isBlack: false, keyChar: 'E' },
  { name: 'F',  semi: 17, isBlack: false, keyChar: 'R' },
  { name: 'F#', semi: 18, isBlack: true,  keyChar: '5' },
  { name: 'G',  semi: 19, isBlack: false, keyChar: 'T' },
  { name: 'G#', semi: 20, isBlack: true,  keyChar: '6' },
  { name: 'A',  semi: 21, isBlack: false, keyChar: 'Y' },
  { name: 'A#', semi: 22, isBlack: true,  keyChar: '7' },
  { name: 'B',  semi: 23, isBlack: false, keyChar: 'U' },
  { name: 'C',  semi: 24, isBlack: false, keyChar: 'I' }
];

// --- 1. Web MIDI Initialization & Port Management ---
async function initMIDI() {
  if (!navigator.requestMIDIAccess) {
    console.warn('Web MIDI API is not supported in this browser.');
    logMidiEvent('SYS', 'HOST', 'SYS', 'Web MIDI not supported in this browser. Use Chrome/Edge.', []);
    showStatusAlert('Web MIDI API not supported. Please use Chrome or Edge.');
    return;
  }

  try {
    const access = await navigator.requestMIDIAccess({ sysex: true });
    state.midiAccess = access;
    access.onstatechange = onMIDIStateChange;
    refreshMIDIPorts();
    logMidiEvent('SYS', 'HOST', 'SYS', 'Web MIDI Access granted successfully.', []);
  } catch (err) {
    console.error('MIDI Access Request Failed:', err);
    logMidiEvent('SYS', 'HOST', 'SYS', `MIDI Access Error: ${err.message}`, []);
    showStatusAlert('Failed to access MIDI devices. Check permissions.');
  }
}

function onMIDIStateChange() {
  refreshMIDIPorts();
}

function refreshMIDIPorts() {
  if (!state.midiAccess) return;

  const selS1 = document.getElementById('selS1Out');
  const selFM1 = document.getElementById('selFM1Out');
  const selIn = document.getElementById('selMidiIn');

  const prevS1Id = state.s1Out ? state.s1Out.id : '';
  const prevFM1Id = state.fm1Out ? state.fm1Out.id : '';
  const prevInId = state.midiIn ? state.midiIn.id : (state.allMidiIn ? 'all' : '');

  selS1.innerHTML = '<option value="">(None / Disconnected)</option>';
  selFM1.innerHTML = '<option value="">(None / Disconnected)</option>';
  if (selIn) {
    selIn.innerHTML = '<option value="all">All MIDI Inputs (Synths &amp; Keys)</option><option value="">(None / Disabled)</option>';
  }

  state.midiOutputs = Array.from(state.midiAccess.outputs.values());
  state.midiInputs = Array.from(state.midiAccess.inputs.values());

  let autoS1Out = null;
  let autoFM1Out = null;
  let autoS1In = null;
  let autoFM1In = null;
  let autoKeyIn = null;

  // 1. Inspect Outputs
  state.midiOutputs.forEach(port => {
    const optS1 = document.createElement('option');
    optS1.value = port.id;
    optS1.textContent = port.name;
    selS1.appendChild(optS1);

    const optFM1 = document.createElement('option');
    optFM1.value = port.id;
    optFM1.textContent = port.name;
    selFM1.appendChild(optFM1);

    const name = port.name.toLowerCase();
    if (name.includes('s-1') || name.includes('aira')) {
      autoS1Out = port;
    }
    if (name.includes('felucca') || name.includes('fm-1') || name.includes('m-vave') || name.includes('s1vave') || name.includes('s1vave')) {
      autoFM1Out = port;
    }
  });

  // 2. Inspect Inputs
  state.midiInputs.forEach(port => {
    if (selIn) {
      const opt = document.createElement('option');
      opt.value = port.id;
      opt.textContent = port.name;
      selIn.appendChild(opt);
    }

    const name = port.name.toLowerCase();
    if (name.includes('s-1') || name.includes('aira')) {
      autoS1In = port;
    } else if (name.includes('felucca') || name.includes('fm-1') || name.includes('m-vave') || name.includes('s1vave') || name.includes('s1vave')) {
      autoFM1In = port;
    } else {
      if (!autoKeyIn) autoKeyIn = port;
    }
  });

  // Assign S-1 Output
  if (prevS1Id && state.midiOutputs.find(p => p.id === prevS1Id)) {
    state.s1Out = state.midiOutputs.find(p => p.id === prevS1Id);
    selS1.value = prevS1Id;
  } else if (autoS1Out) {
    state.s1Out = autoS1Out;
    selS1.value = autoS1Out.id;
  } else {
    state.s1Out = null;
  }

  // Assign FM-1 Output
  if (prevFM1Id && state.midiOutputs.find(p => p.id === prevFM1Id)) {
    state.fm1Out = state.midiOutputs.find(p => p.id === prevFM1Id);
    selFM1.value = prevFM1Id;
  } else if (autoFM1Out) {
    state.fm1Out = autoFM1Out;
    selFM1.value = autoFM1Out.id;
  } else {
    state.fm1Out = null;
  }

  // Assign Inputs & Listeners
  state.s1In = autoS1In;
  state.fm1In = autoFM1In;

  // By default, listen to All MIDI Inputs (or previous selection)
  const targetInId = prevInId || 'all';
  if (selIn) selIn.value = targetInId;
  setMidiInput(targetInId);

  updateIndicators();

  // Auto-request parameter dump if synth is connected
  if (state.fm1Out || state.s1Out) {
    setTimeout(() => {
      requestSynthDump();
    }, 250);
  }
}

function setMidiInput(id) {
  // Clear existing listeners
  state.midiInputs.forEach(p => { p.onmidimessage = null; });
  state.allMidiIn = false;
  state.midiIn = null;

  if (id === 'all') {
    state.allMidiIn = true;
    state.midiInputs.forEach(p => {
      p.onmidimessage = onIncomingMidi;
    });
  } else if (id) {
    const port = state.midiInputs.find(p => p.id === id);
    if (port) {
      state.midiIn = port;
      port.onmidimessage = onIncomingMidi;
    }
  }

  // ALWAYS ensure Roland S-1 and FM-1 inputs are attached so knob movements are read!
  if (state.s1In && state.s1In.onmidimessage !== onIncomingMidi) {
    state.s1In.onmidimessage = onIncomingMidi;
  }
  if (state.fm1In && state.fm1In.onmidimessage !== onIncomingMidi) {
    state.fm1In.onmidimessage = onIncomingMidi;
  }

  updateIndicators();
}

function onIncomingMidi(e) {
  const data = e.data;
  if (!data || data.length < 1) return;
  const status = data[0] & 0xF0;
  const d1 = data[1];
  const d2 = data[2] !== undefined ? data[2] : 0;
  const portName = (e.target && e.target.name) ? e.target.name : 'MIDI';
  const isS1 = /s-1|aira/i.test(portName);
  const isFM1 = /felucca|fm-1|m-vave|s1vave/i.test(portName);
  const srcTag = isS1 ? 'S-1' : (isFM1 ? 'FM-1' : 'KEYS');

  if (status === 0x90 && d2 > 0) {
    // If incoming note is from external keyboard controller, forward directly to synths
    if (!isS1 && !isFM1) {
      sendNoteOn(d1, d2);
    }
    const semi = d1 - (state.octave * 12);
    if (semi >= 0 && semi <= 24) highlightKey(semi, true);
    updateActiveNoteDisplay(getNoteNameWithOctave(d1));
    logMidiEvent('IN', srcTag, 'NOTE', `Note ON ${getNoteNameWithOctave(d1)} Vel ${d2}`, Array.from(data));
  } else if (status === 0x80 || (status === 0x90 && d2 === 0)) {
    if (!isS1 && !isFM1) {
      sendNoteOff(d1);
    }
    const semi = d1 - (state.octave * 12);
    if (semi >= 0 && semi <= 24) highlightKey(semi, false);
    logMidiEvent('IN', srcTag, 'NOTE', `Note OFF ${getNoteNameWithOctave(d1)}`, Array.from(data));
  } else if (status === 0xB0) {
    // CC message received from synth or controller!
    if (d1 === 119) {
      // CC 119 is the dump request marker, ignore incoming echo
      return;
    }

    // READ & UPDATE VALUE IN UI IMMEDIATELY!
    updateSingleParamUI(d1, d2);
    logMidiEvent('IN', srcTag, 'CC', `Param CC ${d1} = ${d2}`, Array.from(data));

    // If paramLink is enabled and message came from one hardware synth, mirror to the other
    if (state.paramLink && (isS1 || isFM1)) {
      const otherTarget = isS1 ? 'fm1' : 's1';
      sendCC(d1, d2, otherTarget);
    }
  } else if (status === 0xE0) {
    if (!isS1 && !isFM1) sendPitchBend(d1, d2);
    logMidiEvent('IN', srcTag, 'PB', `Pitch Bend ${d1}, ${d2}`, Array.from(data));
  } else if (status === 0xC0) {
    // Program change from synth
    const pc = d1;
    state.currentPreset = pc;
    updatePresetUI(pc);
    logMidiEvent('IN', srcTag, 'PC', `Program Change P${(pc + 1).toString().padStart(2, '0')}`, Array.from(data));
    requestSynthDump();
  }
}

function requestSynthDump(target = null) {
  const dest = target || (state.activeTarget === 'both' ? 'fm1' : state.activeTarget);
  const msg = [0xB0, 119, 0];
  let sent = false;

  if (state.fm1Out && (dest === 'both' || dest === 'fm1')) {
    try { state.fm1Out.send(msg); sent = true; } catch (e) { console.error('FM-1 dump request err:', e); }
  }
  if (state.s1Out && (dest === 'both' || dest === 's1')) {
    try { state.s1Out.send(msg); sent = true; } catch (e) { console.error('S-1 dump request err:', e); }
  }

  showStatusAlert('READING VALUES FROM HARDWARE SYNTH...');
  logMidiEvent('OUT', dest, 'DUMP', 'Sent Parameter Dump Request (CC 119)', msg);
}

function updateIndicators() {
  const indS1 = document.getElementById('indS1');
  const indFM1 = document.getElementById('indFM1');
  const indMidiIn = document.getElementById('indMidiIn');

  if (state.s1Out) {
    indS1.classList.add('connected', 's1-color');
    indS1.title = `Connected to: ${state.s1Out.name}`;
  } else {
    indS1.classList.remove('connected', 's1-color');
    indS1.title = 'Roland S-1 not connected';
  }

  if (state.fm1Out) {
    indFM1.classList.add('connected');
    indFM1.title = `Connected to: ${state.fm1Out.name}`;
  } else {
    indFM1.classList.remove('connected');
    indFM1.title = 'M-VAVE FM-1 not connected';
  }

  if (indMidiIn) {
    if (state.allMidiIn || state.midiIn || state.s1In || state.fm1In) {
      indMidiIn.classList.add('connected');
      indMidiIn.title = state.allMidiIn ? 'Listening on all MIDI inputs (Synths + Keys)' : `Listening to: ${state.midiIn ? state.midiIn.name : 'Synths'}`;
    } else {
      indMidiIn.classList.remove('connected');
      indMidiIn.title = 'No MIDI input selected';
    }
  }
}

// --- 2. Low-level MIDI Sender with Routing & Logging ---
function sendCC(cc, value, forceTarget = null) {
  const target = forceTarget || (state.paramLink ? 'both' : state.activeTarget);
  const msg = [0xB0, cc & 0x7F, value & 0x7F];
  state.params[cc] = value;

  if (target === 'both' || target === 's1') {
    if (state.s1Out) {
      try { state.s1Out.send(msg); } catch (e) { console.error('S-1 send err:', e); }
    }
  }

  if (target === 'both' || target === 'fm1') {
    if (state.fm1Out) {
      try { state.fm1Out.send(msg); } catch (e) { console.error('FM-1 send err:', e); }
    }
  }

  logMidiEvent('OUT', target, 'CC', `CC ${cc} = ${value}`, msg);
}

function sendNoteOn(note, velocity = 100, forceTarget = null) {
  const target = forceTarget || state.activeTarget;
  const msg = [0x90, note & 0x7F, velocity & 0x7F];
  state.activeNotes.set(note, velocity);

  if (target === 'both' || target === 's1') {
    if (state.s1Out) {
      try { state.s1Out.send(msg); } catch (e) {}
    }
  }
  if (target === 'both' || target === 'fm1') {
    if (state.fm1Out) {
      try { state.fm1Out.send(msg); } catch (e) {}
    }
  }

  // Trigger synthetic level bounce for monitoring visualizer
  state.synthSimLevel = Math.max(state.synthSimLevel, (velocity / 127) * 0.95);

  logMidiEvent('OUT', target, 'NOTE', `Note ON ${getNoteNameWithOctave(note)} [Vel ${velocity}]`, msg);
}

function sendNoteOff(note, forceTarget = null) {
  const target = forceTarget || state.activeTarget;
  const msg = [0x80, note & 0x7F, 0];
  state.activeNotes.delete(note);

  if (target === 'both' || target === 's1') {
    if (state.s1Out) {
      try { state.s1Out.send(msg); } catch (e) {}
    }
  }
  if (target === 'both' || target === 'fm1') {
    if (state.fm1Out) {
      try { state.fm1Out.send(msg); } catch (e) {}
    }
  }

  logMidiEvent('OUT', target, 'NOTE', `Note OFF ${getNoteNameWithOctave(note)}`, msg);
}

function sendPitchBend(d1, d2, forceTarget = null) {
  const target = forceTarget || state.activeTarget;
  const msg = [0xE0, d1 & 0x7F, d2 & 0x7F];
  if (target === 'both' || target === 's1') {
    if (state.s1Out) { try { state.s1Out.send(msg); } catch (e) {} }
  }
  if (target === 'both' || target === 'fm1') {
    if (state.fm1Out) { try { state.fm1Out.send(msg); } catch (e) {} }
  }
  logMidiEvent('OUT', target, 'PB', `Pitch Bend ${d1}, ${d2}`, msg);
}

function sendProgramChange(progNum, forceTarget = null) {
  // Constrain between 0 and 98 (99 presets, 1-64 for Roland S-1 & FM-1, 65-99 for S1Vave User)
  progNum = Math.max(0, Math.min(98, progNum));
  const target = forceTarget || state.activeTarget;
  const msg = [0xC0, progNum & 0x7F];

  if (target === 'both' || target === 's1') {
    if (state.s1Out) {
      try { state.s1Out.send(msg); } catch (e) { console.error('S-1 PC send err:', e); }
    }
  }

  if (target === 'both' || target === 'fm1') {
    if (state.fm1Out) {
      try { state.fm1Out.send(msg); } catch (e) { console.error('FM-1 PC send err:', e); }
    }
  }

  state.currentPreset = progNum;
  updatePresetUI(progNum);

  const bank = Math.floor(progNum / 16) + 1;
  const pat = (progNum % 16) + 1;
  const s1Tag = (progNum < 64) ? ` [Bank ${bank}-${pat}]` : ' [User Preset]';
  const pName = `P${(progNum + 1).toString().padStart(2, '0')}`;

  showStatusAlert(`PROGRAM CHANGE: ${pName}${s1Tag}`);
  logMidiEvent('OUT', target, 'PC', `Program Change ${pName}${s1Tag}`, msg);
}

function updatePresetUI(progNum) {
  const sel = document.getElementById('selPreset');
  if (sel && sel.value !== String(progNum)) {
    sel.value = String(progNum);
  }
}

function initPresetDropdown() {
  const sel = document.getElementById('selPreset');
  if (!sel) return;
  sel.innerHTML = '';

  // 1-64: Standard Banks 1 to 4 (16 patterns each)
  for (let i = 0; i < 64; i++) {
    const bank = Math.floor(i / 16) + 1;
    const pat = (i % 16) + 1;
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `P${(i + 1).toString().padStart(2, '0')} [Bank ${bank}-${pat}]`;
    sel.appendChild(opt);
  }

  // 65-99: S1Vave Extended Presets
  for (let i = 64; i < 99; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `P${(i + 1).toString().padStart(2, '0')} [User Sound ${i - 63}]`;
    sel.appendChild(opt);
  }

  sel.value = String(state.currentPreset);

  sel.addEventListener('change', (e) => {
    sendProgramChange(parseInt(e.target.value, 10));
  });

  const btnPrev = document.getElementById('btnPrevPreset');
  if (btnPrev) {
    btnPrev.addEventListener('click', () => {
      sendProgramChange(state.currentPreset - 1);
    });
  }

  const btnNext = document.getElementById('btnNextPreset');
  if (btnNext) {
    btnNext.addEventListener('click', () => {
      sendProgramChange(state.currentPreset + 1);
    });
  }
}

function panicAllNotes() {
  [state.s1Out, state.fm1Out].forEach(port => {
    if (port) {
      try {
        port.send([0xB0, 120, 0]); // All Sound Off
        port.send([0xB0, 123, 0]); // All Notes Off
        for (let n = 24; n <= 108; n++) {
          port.send([0x80, n, 0]);
        }
      } catch (e) {}
    }
  });

  stopSequence();
  stopArpClock();
  state.arp.heldNotes = [];
  state.arp.latchedNotes = [];
  state.latchedNotes.clear();
  state.activeNotes.clear();
  document.querySelectorAll('.key-white, .key-black').forEach(el => el.classList.remove('active'));
  updateActiveNoteDisplay('ALL SOUND OFF (PANIC)');
  logMidiEvent('SYS', 'ALL', 'SYS', 'PANIC: All Sound Off (CC 120), All Notes Off (CC 123)', [0xB0, 120, 0]);
}

// --- 3. Live MIDI Traffic Event Logger ---
function logMidiEvent(direction, target, type, desc, rawBytes = []) {
  const stream = document.getElementById('midiLogStream');
  if (!stream) return;

  // Filter check
  const isNote = type === 'NOTE';
  const isCC = type === 'CC' || type === 'PB' || type === 'PC';
  const isSys = type === 'SYS';

  const entry = document.createElement('div');
  entry.className = `log-entry ${direction.toLowerCase()} ${type.toLowerCase()}`;
  entry.setAttribute('data-type', isNote ? 'note' : (isCC ? 'cc' : 'sys'));

  const now = new Date();
  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;

  const hexBytes = rawBytes && rawBytes.length > 0 
    ? rawBytes.map(b => '0x' + (b & 0xFF).toString(16).padStart(2, '0').toUpperCase()).join(' ')
    : '';

  entry.innerHTML = `[${timeStr}] [${direction}] [${target}] [${type}] ${desc} ${hexBytes ? `<span style="color:#6f8396">(${hexBytes})</span>` : ''}`;

  if (state.midiFilter !== 'all') {
    if (state.midiFilter === 'note' && !isNote) entry.style.display = 'none';
    if (state.midiFilter === 'cc' && !isCC) entry.style.display = 'none';
  }

  stream.appendChild(entry);
  state.midiLogCount++;

  // Prune history to keep memory bounded
  if (stream.children.length > 120) {
    stream.removeChild(stream.firstElementChild);
  }

  // Auto-scroll
  stream.scrollTop = stream.scrollHeight;
}

function setupMidiLogControls() {
  const filterBtns = document.querySelectorAll('.midi-log-controls .filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.getAttribute('data-filter');
      state.midiFilter = filter;

      const entries = document.querySelectorAll('#midiLogStream .log-entry');
      entries.forEach(entry => {
        const type = entry.getAttribute('data-type');
        if (filter === 'all') {
          entry.style.display = '';
        } else if (filter === 'note') {
          entry.style.display = (type === 'note') ? '' : 'none';
        } else if (filter === 'cc') {
          entry.style.display = (type === 'cc') ? '' : 'none';
        }
      });
    });
  });

  const clearBtn = document.getElementById('btnClearMidiLog');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      const stream = document.getElementById('midiLogStream');
      if (stream) {
        stream.innerHTML = '<div class="log-entry system">[SYS] MIDI Event Log Cleared.</div>';
      }
    });
  }
}

// --- 4. Target Selection & Instant A/B Toggle ---
function setTarget(target) {
  state.activeTarget = target;
  document.getElementById('btnBoth').classList.toggle('active', target === 'both');
  document.getElementById('btnS1').classList.toggle('active', target === 's1');
  document.getElementById('btnFM1').classList.toggle('active', target === 'fm1');
  setAudioRoute(target);
}

function toggleAB() {
  const prevTarget = state.activeTarget;
  const newTarget = (prevTarget === 's1') ? 'fm1' : 's1';

  // Transfer active sounding notes smoothly
  const currentSoundingNotes = Array.from(state.latchedNotes);
  currentSoundingNotes.forEach(note => {
    sendNoteOff(note, prevTarget);
  });

  setTarget(newTarget);

  currentSoundingNotes.forEach(note => {
    sendNoteOn(note, state.velocity, newTarget);
  });
}

// --- 5. Parameter UI Binding ---
function formatSliderVal(id, val) {
  if (id === 'slTone') return (val - 64 > 0 ? '+' : '') + (val - 64);
  if (id === 'slWarmth') return `${Math.round(val * 100 / 127)}%`;
  if (id === 'slTune') return (val - 64 > 0 ? '+' : '') + (val - 64);
  if (id === 'slTranspose') return (val - 60 > 0 ? '+' : '') + (val - 60) + ' ST';
  if (id === 'slChordKs2' || id === 'slChordKs3' || id === 'slChordKs4') {
    return (val - 12 > 0 ? '+' : '') + (val - 12) + ' ST';
  }
  if (id === 'slOscBend' || id === 'slFltBend') return `${val} ST`;
  if (id === 'slRevPre') return `${val} ms`;
  if (id === 'slTempo') return `${val} BPM`;
  if (id === 'slRiserShape') return `${val}%`;
  if (id === 'slDrawMult' || id === 'slChopComb') return `${val + 1}.0x`;
  if (id === 'slChopOvtn') {
    if (val === 0) return 'OFF (0)';
    if (val === 100) return 'MUTE (100)';
    if (val > 100) return `${val} (REV)`;
    return val;
  }
  return val;
}

function setupSliders() {
  document.querySelectorAll('input[type=range][data-cc]').forEach(slider => {
    const cc = parseInt(slider.getAttribute('data-cc'), 10);
    const id = slider.id;
    const valSpanId = 'val' + id.replace('sl', '');
    const valSpan = document.getElementById(valSpanId);

    slider.addEventListener('input', () => {
      const val = parseInt(slider.value, 10);
      if (valSpan) valSpan.textContent = formatSliderVal(id, val);
      sendCC(cc, val);
      
      // If ADSR sliders changed, update the interactive contour canvas
      if (['slAtt', 'slDec', 'slSus', 'slRel'].includes(id)) {
        drawEnvCurve();
      }
    });
  });
}

function setupButtonGroups() {
  setupGroup('grpRange', 14, val => val);         // 0=64', 1=32', 2=16', 3=8', 4=4', 5=2'
  setupGroup('grpPwmSrc', 16, val => val);        // 0=ENV, 1=MAN, 2=LFO
  setupGroup('grpSubType', 22, val => val);       // 0=-2o.A, 1=-2oc, 2=-1oc
  setupGroup('grpDrawSw', 107, val => val);       // 0=OFF, 1=STEP, 2=SLOPE
  setupGroup('grpNoiseMode', 78, val => val);     // 0=PINK, 1=WHITE
  setupGroup('grpFltColor', 108, val => val);     // 0=S-1 CLEAN, 1=MIDNIGHT WARM
  setupGroup('grpAmpMode', 28, val => val);       // 0=GATE, 1=ENV
  setupGroup('grpEnvTrg', 29, val => val);        // 0=LFO, 1=GATE, 2=GATE+TRIG
  setupGroup('grpLfoWave', 12, val => val);       // 0=SAW, 1=INV, 2=TRI, 3=SQR, 4=RND, 5=NOI
  setupGroup('grpLfoMode', 79, val => val);       // 0=NORM, 1=FAST
  setupGroup('grpLfoSync', 106, val => val);      // 0=OFF, 1=ON
  setupGroup('grpLfoTrig', 105, val => val);      // 0=OFF, 1=ON
  setupGroup('grpRiserMode', 32, val => {
    sendCC(78, val); // Roland S-1 compatibility
    return val;
  });
  setupGroup('grpChoMode', 93, val => val);       // 0=OFF, 1=1, 2=2, 3=3, 4=4
  setupGroup('grpDlySync', 37, val => val);       // 0=OFF, 1=ON
  setupGroup('grpRevType', 38, val => val);       // 0=AMB, 1=ROOM, 2=HALL1, 3=HALL2, 4=PLATE, 5=SPRING, 6=MOD
  setupGroup('grpPolyMode', 80, val => val);      // 0=MONO, 1=UNISON (8V), 2=POLY (8V), 3=CHORD
  setupGroup('grpPortaMode', 31, val => val);     // 0=OFF, 1=ON, 2=AUTO
  setupGroup('grpPortaSw', 65, val => val);       // 0=OFF, 1=ON
  setupGroup('grpSustainPedal', 64, val => (val ? 127 : 0)); // 0=OFF, 127=HOLD
  setupGroup('grpLfoTrig', 105, val => val);      // 0=OFF, 1=ON
  setupGroup('grpChordSw2', 81, val => val);      // 0=OFF, 1=ON
  setupGroup('grpChordSw3', 82, val => val);      // 0=OFF, 1=ON
  setupGroup('grpChordSw4', 83, val => val);      // 0=OFF, 1=ON
  setupGroup('grpArpSw', 111, val => (val ? 127 : 0), (val, ccVal) => {
    state.arp.on = (val === 1);
    logMidiEvent('SYS', 'ALL', 'ARP', `Hardware Arpeggiator ${val ? 'ON' : 'OFF'} (CC 111=${ccVal})`, []);
  });
  setupGroup('grpArpHold', 114, val => (val ? 127 : 0), (val, ccVal) => {
    state.arp.hold = (val === 1);
    logMidiEvent('SYS', 'ALL', 'ARP', `Arp Hold ${val ? 'ON' : 'OFF'} (CC 114=${ccVal})`, []);
  });
  setupGroup('grpArpType', 112, val => val, (val) => {
    state.arp.type = val;
    logMidiEvent('SYS', 'ALL', 'ARP', `Arp Type ${val} (CC 112=${val})`, []);
  });
  setupGroup('grpArpRate', 113, val => val, (val) => {
    state.arp.rate = val;
    logMidiEvent('SYS', 'ALL', 'ARP', `Arp Rate ${val} (CC 113=${val})`, []);
  });
  setupGroup('grpArpPri', 116, val => (val ? 127 : 0), (val) => {
    state.arp.pri = val;
    logMidiEvent('SYS', 'ALL', 'ARP', `Arp Note Priority ${val ? 'LOW' : 'LAST'} (CC 116)`, []);
  });
  setupGroup('grpSeqPlay', 117, val => (val ? 127 : 0), (val) => {
    logMidiEvent('SYS', 'ALL', 'SEQ', `Synth Hardware Sequencer ${val ? 'PLAY' : 'STOP'} (CC 117)`, []);
  });
  setupGroup('grpTrackSel', 118, val => (val ? 127 : 0), (val) => {
    logMidiEvent('SYS', 'ALL', 'PART', `Active Synth Part ${val ? 'TRACK B' : 'TRACK A'} (CC 118)`, []);
  });
}

function setupGroup(containerId, cc, valMapper, callback = null) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const buttons = container.querySelectorAll('.opt-btn');

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const idx = parseInt(btn.getAttribute('data-val'), 10);
      const ccVal = valMapper ? valMapper(idx) : idx;
      if (cc !== null && cc !== undefined) sendCC(cc, ccVal);
      if (callback) callback(idx, ccVal);
    });
  });
}

function updateSliderUI(sliderId, value) {
  const sl = document.getElementById(sliderId);
  if (sl) {
    sl.value = value;
    const valSpanId = 'val' + sliderId.replace('sl', '');
    const valSpan = document.getElementById(valSpanId);
    if (valSpan) valSpan.textContent = formatSliderVal(sliderId, value);
  }
}

function updateGroupUI(containerId, activeIdx) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const buttons = container.querySelectorAll('.opt-btn');
  buttons.forEach(b => {
    b.classList.toggle('active', parseInt(b.getAttribute('data-val'), 10) === activeIdx);
  });
}

function updateSingleParamUI(cc, val) {
  state.params[cc] = val;

  // 1. Slider controls with exact matching ID
  if (cc === 20) updateSliderUI('slSaw', val);
  else if (cc === 19) updateSliderUI('slPulse', val);
  else if (cc === 15) updateSliderUI('slPw', val);
  else if (cc === 21) updateSliderUI('slSub', val);
  else if (cc === 23) updateSliderUI('slNoise', val);
  else if (cc === 76) updateSliderUI('slTune', val);
  else if (cc === 18) updateSliderUI('slOscBend', val);
  else if (cc === 102) updateSliderUI('slDrawMult', val);
  else if (cc === 103) updateSliderUI('slChopOvtn', val);
  else if (cc === 104) updateSliderUI('slChopComb', val);
  else if (cc === 109) updateSliderUI('slTone', val);
  else if (cc === 110) updateSliderUI('slWarmth', val);
  else if (cc === 74) updateSliderUI('slCutoff', val);
  else if (cc === 71) updateSliderUI('slReso', val);
  else if (cc === 24) updateSliderUI('slFenv', val);
  else if (cc === 25) updateSliderUI('slFlfo', val);
  else if (cc === 26) updateSliderUI('slKeytrk', val);
  else if (cc === 27) updateSliderUI('slFltBend', val);
  else if (cc === 73) updateSliderUI('slAtt', val);
  else if (cc === 75) updateSliderUI('slDec', val);
  else if (cc === 30) updateSliderUI('slSus', val);
  else if (cc === 72) updateSliderUI('slRel', val);
  else if (cc === 3) updateSliderUI('slLfoRate', val);
  else if (cc === 13) updateSliderUI('slLfoPitch', val);
  else if (cc === 1) updateSliderUI('slModDepth', val);
  else if (cc === 33) updateSliderUI('slRiserReso', val);
  else if (cc === 34) updateSliderUI('slRiserShape', val);
  else if (cc === 35) updateSliderUI('slRiserLvl', val);
  else if (cc === 92) updateSliderUI('slDlyLvl', val);
  else if (cc === 90) updateSliderUI('slDlyTime', val);
  else if (cc === 36) updateSliderUI('slDlyFb', val);
  else if (cc === 91) updateSliderUI('slRevLvl', val);
  else if (cc === 89) updateSliderUI('slRevTime', val);
  else if (cc === 39) updateSliderUI('slRevPre', val);
  else if (cc === 5) updateSliderUI('slPortaTime', val);
  else if (cc === 77) updateSliderUI('slTranspose', val);
  else if (cc === 7) updateSliderUI('slVol', val);
  else if (cc === 85) updateSliderUI('slChordKs2', val);
  else if (cc === 86) updateSliderUI('slChordKs3', val);
  else if (cc === 87) updateSliderUI('slChordKs4', val);

  // 2. Button groups with exact matching CC
  if (cc === 14) updateGroupUI('grpRange', val);
  else if (cc === 16) updateGroupUI('grpPwmSrc', val);
  else if (cc === 22) updateGroupUI('grpSubType', val);
  else if (cc === 107) updateGroupUI('grpDrawSw', val);
  else if (cc === 78) {
    updateGroupUI('grpNoiseMode', val);
    updateGroupUI('grpRiserMode', val);
  }
  else if (cc === 108) updateGroupUI('grpFltColor', val);
  else if (cc === 28) updateGroupUI('grpAmpMode', val);
  else if (cc === 29) updateGroupUI('grpEnvTrg', val);
  else if (cc === 12) updateGroupUI('grpLfoWave', val);
  else if (cc === 79) updateGroupUI('grpLfoMode', val);
  else if (cc === 106) updateGroupUI('grpLfoSync', val);
  else if (cc === 105) updateGroupUI('grpLfoTrig', val);
  else if (cc === 32) updateGroupUI('grpRiserMode', val);
  else if (cc === 93) updateGroupUI('grpChoMode', val);
  else if (cc === 37) updateGroupUI('grpDlySync', val);
  else if (cc === 38) updateGroupUI('grpRevType', val);
  else if (cc === 80) updateGroupUI('grpPolyMode', val);
  else if (cc === 31) updateGroupUI('grpPortaMode', val);
  else if (cc === 65) updateGroupUI('grpPortaSw', val);
  else if (cc === 64) updateGroupUI('grpSustainPedal', val >= 64 ? 1 : 0);
  else if (cc === 81) updateGroupUI('grpChordSw2', val);
  else if (cc === 82) updateGroupUI('grpChordSw3', val);
  else if (cc === 83) updateGroupUI('grpChordSw4', val);
  else if (cc === 111) {
    const sw = val >= 64 ? 1 : 0;
    state.arp.on = (sw === 1);
    updateGroupUI('grpArpSw', sw);
  }
  else if (cc === 112) {
    const t = val % 8;
    state.arp.type = t;
    updateGroupUI('grpArpType', t);
  }
  else if (cc === 113) {
    const r = val % 7;
    state.arp.rate = r;
    updateGroupUI('grpArpRate', r);
  }
  else if (cc === 114) {
    const h = val >= 64 ? 1 : 0;
    state.arp.hold = (h === 1);
    updateGroupUI('grpArpHold', h);
  }
  else if (cc === 115) {
    const t = val < 40 ? 40 : (val > 240 ? 240 : val);
    state.arp.tempo = t;
    updateSliderUI('slTempo', t);
  }
  else if (cc === 116) {
    const p = val >= 64 ? 1 : 0;
    state.arp.pri = p;
    updateGroupUI('grpArpPri', p);
  }
  else if (cc === 117) {
    updateGroupUI('grpSeqPlay', val >= 64 ? 1 : 0);
  }
  else if (cc === 118) {
    updateGroupUI('grpTrackSel', val >= 64 ? 1 : 0);
  }

  // 3. Fallback generic slider lookup in case data-cc exists
  const genericSlider = document.querySelector(`input[type=range][data-cc="${cc}"]`);
  if (genericSlider && genericSlider.value != val) {
    genericSlider.value = val;
    const valSpan = document.getElementById('val' + genericSlider.id.replace('sl', ''));
    if (valSpan) valSpan.textContent = formatSliderVal(genericSlider.id, val);
  }

  // 4. Redraw ADSR envelope curve canvas if envelope parameters changed
  if ([73, 75, 30, 72].includes(cc)) {
    drawEnvCurve();
  }
}

function applyPatch(patch, target = null) {
  Object.entries(patch).forEach(([ccStr, val]) => {
    const cc = parseInt(ccStr, 10);
    sendCC(cc, val, target);
    updateSingleParamUI(cc, val);
  });
}

// --- 6. Performance & Patch Action Toolbar ---
const BASELINE_INIT_PATCH = {
  14: 3,    // 8'
  20: 127,  // Pure Saw
  19: 0,
  15: 0,
  16: 1,
  21: 0,
  22: 2,
  23: 0,
  18: 2,    // Bend sens 2 semitones
  76: 64,   // Master tune 0
  78: 0,
  107: 0,
  102: 0,
  103: 0,
  104: 0,
  108: 0,   // S-1 Clean
  109: 64,  // Tone tilt 0
  110: 0,   // Warmth 0
  74: 127,  // Cutoff open
  71: 0,    // Reso 0
  24: 0,
  25: 0,
  26: 64,
  27: 2,
  73: 0,    // Attack 0
  75: 64,   // Decay 64
  30: 127,  // Sustain 127
  72: 30,   // Release 30
  28: 1,    // Env
  29: 2,    // Gate+Trig
  12: 2,    // Tri
  3: 60,
  13: 0,
  1: 15,
  79: 0,
  106: 0,
  105: 0,
  32: 0,    // Riser Mode OFF
  33: 30,   // Riser Reso
  34: 0,    // Riser Shape Saw
  35: 80,   // Riser Lvl
  93: 0,    // Chorus Off
  92: 0,    // Delay Off
  90: 50,
  36: 50,
  37: 1,    // Delay Sync ON
  91: 0,    // Reverb Off
  89: 100,
  38: 5,    // Reverb Type Plate
  39: 20,   // Reverb Pre-delay
  80: 0,    // Mono
  31: 0,    // Porta Off
  65: 0,    // Porta Switch OFF
  64: 0,    // Sustain Pedal OFF
  5: 30,
  77: 60,   // Transpose 0
  7: 90,
  81: 1,    // Chord V2 ON
  85: 12,   // Chord V2 Shift 0
  82: 1,    // Chord V3 ON
  86: 12,   // Chord V3 Shift 0
  83: 1,    // Chord V4 ON
  87: 12    // Chord V4 Shift 0
};

function setupPatchToolbar() {
  // 0. Read from Synth (CC 119 Dump)
  const btnRead = document.getElementById('btnReadSynth');
  if (btnRead) {
    btnRead.addEventListener('click', () => {
      requestSynthDump();
    });
  }

  // 1. Init Patch
  const btnInit = document.getElementById('btnInitPatch');
  if (btnInit) {
    btnInit.addEventListener('click', () => {
      applyPatch(BASELINE_INIT_PATCH);
      showStatusAlert('INITIALIZED TO CLEAN BASELINE PATCH');
      logMidiEvent('SYS', 'ALL', 'SYS', 'Patch Initialized to clean baseline sound.', []);
    });
  }

  // 2. Randomize
  const btnRandom = document.getElementById('btnRandomize');
  if (btnRandom) {
    btnRandom.addEventListener('click', () => {
      const randomPatch = {
        14: Math.floor(Math.random() * 4) + 1, // 32', 16', 8', 4'
        20: Math.floor(Math.random() * 128),
        19: Math.floor(Math.random() * 128),
        15: Math.floor(Math.random() * 90),
        16: Math.floor(Math.random() * 3),
        21: Math.random() > 0.4 ? Math.floor(Math.random() * 100) : 0,
        22: Math.floor(Math.random() * 3),
        23: Math.random() > 0.7 ? Math.floor(Math.random() * 60) : 0,
        107: 0,
        102: 0,
        103: 0,
        104: 0,
        108: Math.random() > 0.5 ? 1 : 0,
        74: Math.floor(Math.random() * 85) + 30, // Cutoff 30..115
        71: Math.floor(Math.random() * 85),      // Reso 0..85
        24: Math.floor(Math.random() * 95),      // Env Depth
        25: Math.random() > 0.6 ? Math.floor(Math.random() * 60) : 0,
        73: Math.floor(Math.random() * 35),      // Snappy to medium attack
        75: Math.floor(Math.random() * 80) + 20, // Decay
        30: Math.floor(Math.random() * 128),     // Sustain
        72: Math.floor(Math.random() * 70) + 15, // Release
        28: 1,
        29: 2,
        12: Math.floor(Math.random() * 6),
        3: Math.floor(Math.random() * 90) + 15,
        13: Math.random() > 0.7 ? Math.floor(Math.random() * 40) : 0,
        93: Math.random() > 0.6 ? Math.floor(Math.random() * 5) : 0,
        92: Math.random() > 0.5 ? Math.floor(Math.random() * 50) : 0,
        90: Math.floor(Math.random() * 80) + 20,
        36: Math.floor(Math.random() * 60) + 20,
        91: Math.random() > 0.5 ? Math.floor(Math.random() * 50) : 0,
        89: Math.floor(Math.random() * 70) + 40,
        80: Math.floor(Math.random() * 3) // Mono, Unison, Poly
      };

      // Ensure at least one osc is audible
      if (randomPatch[20] < 30 && randomPatch[19] < 30) {
        randomPatch[20] = 110;
      }

      applyPatch(randomPatch);
      showStatusAlert('GENERATED MUSICAL RANDOM PATCH');
      logMidiEvent('SYS', 'ALL', 'SYS', 'Random musical patch generated & dispatched.', []);
    });
  }

  // 3. Copy A -> B (Roland S-1 to M-VAVE FM-1)
  const btnCopyAtoB = document.getElementById('btnCopyAtoB');
  if (btnCopyAtoB) {
    btnCopyAtoB.addEventListener('click', () => {
      applyPatch(state.params, 'fm1');
      showStatusAlert('COPIED S-1 PARAMETERS TO M-VAVE FM-1');
      logMidiEvent('SYS', 'FM1', 'SYS', 'Copy A -> B: Sent all current parameters to FM-1.', []);
    });
  }

  // 4. Copy B -> A (M-VAVE FM-1 to Roland S-1)
  const btnCopyBtoA = document.getElementById('btnCopyBtoA');
  if (btnCopyBtoA) {
    btnCopyBtoA.addEventListener('click', () => {
      applyPatch(state.params, 's1');
      showStatusAlert('COPIED FM-1 PARAMETERS TO ROLAND S-1');
      logMidiEvent('SYS', 'S1', 'SYS', 'Copy B -> A: Sent all current parameters to S-1.', []);
    });
  }

  // 5. Export JSON
  const btnExport = document.getElementById('btnExportJson');
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      const patchData = {
        name: 'S1Vave Patch',
        version: '1.0',
        author: 'Andrew GG',
        timestamp: new Date().toISOString(),
        params: state.params
      };

      const blob = new Blob([JSON.stringify(patchData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `s1vave_patch_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      showStatusAlert('PATCH EXPORTED TO JSON FILE');
      logMidiEvent('SYS', 'HOST', 'SYS', `Exported patch (${Object.keys(state.params).length} CCs) to JSON.`, []);
    });
  }

  // 6. Import JSON
  const btnImport = document.getElementById('btnImportJson');
  const fileInput = document.getElementById('fileImportJson');
  if (btnImport && fileInput) {
    btnImport.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target.result);
          const incomingParams = parsed.params || parsed;
          applyPatch(incomingParams);
          showStatusAlert(`IMPORTED PATCH: ${parsed.name || file.name}`);
          logMidiEvent('SYS', 'ALL', 'SYS', `Imported patch from ${file.name}.`, []);
        } catch (err) {
          console.error('Failed to parse JSON patch:', err);
          showStatusAlert('ERROR: Invalid JSON Patch file format.');
        }
      };
      reader.readAsText(file);
      fileInput.value = '';
    });
  }

  // 7. Toggle Monitoring Deck
  const btnToggleMon = document.getElementById('btnToggleMonitor');
  const monDeck = document.getElementById('monitoringDeck');
  if (btnToggleMon && monDeck) {
    btnToggleMon.addEventListener('click', () => {
      const isCollapsed = monDeck.classList.toggle('collapsed');
      btnToggleMon.classList.toggle('active', !isCollapsed);
    });
  }

  // 8. Panic
  const btnPanic = document.getElementById('btnPanic');
  if (btnPanic) {
    btnPanic.addEventListener('click', () => {
      stopSequence();
      panicAllNotes();
    });
  }
}

// --- 7. Interactive ADSR Contour Canvas ---
function drawEnvCurve() {
  const canvas = document.getElementById('envCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  // Background subtle grid
  ctx.strokeStyle = '#182026';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5);
  ctx.stroke();

  const att = parseInt(document.getElementById('slAtt')?.value || state.params[73] || 0, 10);
  const dec = parseInt(document.getElementById('slDec')?.value || state.params[75] || 64, 10);
  const sus = parseInt(document.getElementById('slSus')?.value || state.params[30] || 127, 10);
  const rel = parseInt(document.getElementById('slRel')?.value || state.params[72] || 30, 10);

  // Scale time segments
  const totalWeight = (att + 5) + (dec + 5) + 30 + (rel + 5);
  const padL = 6;
  const padR = w - 6;
  const padT = 6;
  const padB = h - 6;
  const usableW = padR - padL;
  const usableH = padB - padT;

  const x0 = padL;
  const y0 = padB;

  const wAtt = ((att + 5) / totalWeight) * usableW;
  const wDec = ((dec + 5) / totalWeight) * usableW;
  const wSus = (30 / totalWeight) * usableW;
  const wRel = ((rel + 5) / totalWeight) * usableW;

  const x1 = x0 + wAtt;
  const y1 = padT; // Peak

  const x2 = x1 + wDec;
  const y2 = padB - ((sus / 127) * usableH); // Sustain level

  const x3 = x2 + wSus;
  const y3 = y2;

  const x4 = x3 + wRel;
  const y4 = padB;

  // Draw gradient fill
  const grad = ctx.createLinearGradient(0, padT, 0, padB);
  grad.addColorStop(0, 'rgba(0, 229, 163, 0.28)');
  grad.addColorStop(1, 'rgba(0, 229, 163, 0.02)');

  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.lineTo(x1, y1);
  // Exponential decay curve
  ctx.quadraticCurveTo(x1 + (wDec * 0.3), y1 + ((y2 - y1) * 0.8), x2, y2);
  ctx.lineTo(x3, y3);
  // Exponential release curve
  ctx.quadraticCurveTo(x3 + (wRel * 0.3), y3 + ((y4 - y3) * 0.8), x4, y4);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw stroke curve
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.lineTo(x1, y1);
  ctx.quadraticCurveTo(x1 + (wDec * 0.3), y1 + ((y2 - y1) * 0.8), x2, y2);
  ctx.lineTo(x3, y3);
  ctx.quadraticCurveTo(x3 + (wRel * 0.3), y3 + ((y4 - y3) * 0.8), x4, y4);

  ctx.strokeStyle = '#00e5a3';
  ctx.lineWidth = 2;
  ctx.shadowColor = 'rgba(0, 229, 163, 0.6)';
  ctx.shadowBlur = 6;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Node markers
  const drawNode = (x, y) => {
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fill();
  };
  drawNode(x1, y1);
  drawNode(x2, y2);
  drawNode(x3, y3);
}

// --- 8. Real-Time VU Meters & CRT Oscilloscope ---
function setupAudioInput() {
  const btnAudioInput = document.getElementById('btnAudioInput');
  if (btnAudioInput) {
    btnAudioInput.addEventListener('click', () => {
      toggleAudioRouting();
    });
  }
}

function startVisualizerLoop() {
  const scopeCanvas = document.getElementById('liveScopeCanvas');
  const vuFM1L = document.getElementById('vuFM1L');
  if (!scopeCanvas && !vuFM1L) return;
  const ctx = scopeCanvas ? scopeCanvas.getContext('2d') : null;
  const timeData = new Uint8Array(256);

  const vuS1L = document.getElementById('vuS1L');
  const vuS1R = document.getElementById('vuS1R');
  const peakS1L = document.getElementById('peakS1L');
  const peakS1R = document.getElementById('peakS1R');

  const vuFM1R = document.getElementById('vuFM1R');
  const peakFM1L = document.getElementById('peakFM1L');
  const peakFM1R = document.getElementById('peakFM1R');

  function renderFrame() {
    requestAnimationFrame(renderFrame);

    let levelS1 = 0;
    let levelFM1 = 0;

    // 1. Calculate Levels
    if (state.micActive && state.analyserNode) {
      state.analyserNode.getByteTimeDomainData(timeData);

      let sum = 0;
      for (let i = 0; i < timeData.length; i++) {
        const val = (timeData[i] - 128) / 128;
        sum += val * val;
      }
      const rms = Math.sqrt(sum / timeData.length);
      const measured = Math.min(1.0, rms * 4.5);

      if (state.activeTarget === 'both') {
        levelS1 = measured;
        levelFM1 = measured;
      } else if (state.activeTarget === 's1') {
        levelS1 = measured;
        levelFM1 = 0;
      } else if (state.activeTarget === 'fm1') {
        levelS1 = 0;
        levelFM1 = measured;
      }
    } else {
      // Synthetic event-driven envelope & level simulation
      const noteCount = state.activeNotes.size + (state.seqInterval ? 1 : 0);
      if (noteCount > 0) {
        state.synthSimLevel = Math.min(0.95, state.synthSimLevel + 0.15);
      } else {
        state.synthSimLevel = Math.max(0, state.synthSimLevel * 0.92 - 0.005);
      }

      // Add gentle random analog flutter
      const flutter = (Math.random() - 0.5) * 0.04 * (state.synthSimLevel > 0 ? 1 : 0);
      const targetLevel = Math.max(0, Math.min(1.0, state.synthSimLevel + flutter));

      if (state.activeTarget === 'both') {
        levelS1 = targetLevel;
        levelFM1 = targetLevel * 0.98;
      } else if (state.activeTarget === 's1') {
        levelS1 = targetLevel;
        levelFM1 = 0;
      } else if (state.activeTarget === 'fm1') {
        levelS1 = 0;
        levelFM1 = targetLevel;
      }
    }

    // 2. Update VU Meters with Peak Decay
    const updateMeter = (curL, curR, targetVal, vuElL, vuElR, peakElL, peakElR, tracker) => {
      // Smooth decay
      tracker.curL = tracker.curL * 0.75 + targetVal * 0.25;
      tracker.curR = tracker.curR * 0.75 + targetVal * 0.97 * 0.25;

      tracker.peakL = Math.max(tracker.curL, tracker.peakL * 0.975 - 0.005);
      tracker.peakR = Math.max(tracker.curR, tracker.peakR * 0.975 - 0.005);

      const pctL = Math.min(100, Math.round(tracker.curL * 100));
      const pctR = Math.min(100, Math.round(tracker.curR * 100));
      const peakPctL = Math.min(100, Math.round(tracker.peakL * 100));
      const peakPctR = Math.min(100, Math.round(tracker.peakR * 100));

      if (vuElL) vuElL.style.height = `${pctL}%`;
      if (vuElR) vuElR.style.height = `${pctR}%`;
      if (peakElL) peakElL.style.bottom = `${peakPctL}%`;
      if (peakElR) peakElR.style.bottom = `${peakPctR}%`;
    };

    updateMeter(state.vuLevels.s1L, state.vuLevels.s1R, levelS1, vuS1L, vuS1R, peakS1L, peakS1R, {
      get curL() { return state.vuLevels.s1L; }, set curL(v) { state.vuLevels.s1L = v; },
      get curR() { return state.vuLevels.s1R; }, set curR(v) { state.vuLevels.s1R = v; },
      get peakL() { return state.vuLevels.s1PeakL; }, set peakL(v) { state.vuLevels.s1PeakL = v; },
      get peakR() { return state.vuLevels.s1PeakR; }, set peakR(v) { state.vuLevels.s1PeakR = v; }
    });

    updateMeter(state.vuLevels.fm1L, state.vuLevels.fm1R, levelFM1, vuFM1L, vuFM1R, peakFM1L, peakFM1R, {
      get curL() { return state.vuLevels.fm1L; }, set curL(v) { state.vuLevels.fm1L = v; },
      get curR() { return state.vuLevels.fm1R; }, set curR(v) { state.vuLevels.fm1R = v; },
      get peakL() { return state.vuLevels.fm1PeakL; }, set peakL(v) { state.vuLevels.fm1PeakL = v; },
      get peakR() { return state.vuLevels.fm1PeakR; }, set peakR(v) { state.vuLevels.fm1PeakR = v; }
    });

    // 3. Render CRT Oscilloscope
    if (ctx && scopeCanvas) {
      const sw = scopeCanvas.width;
      const sh = scopeCanvas.height;
      const midY = sh / 2;

      // Dark background with slight motion trail
      ctx.fillStyle = 'rgba(8, 10, 11, 0.45)';
      ctx.fillRect(0, 0, sw, sh);

      // Draw CRT Graticule Lines
      ctx.strokeStyle = 'rgba(26, 34, 40, 0.7)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      // Center crosshair
      ctx.moveTo(0, midY); ctx.lineTo(sw, midY);
      ctx.moveTo(sw / 2, 0); ctx.lineTo(sw / 2, sh);
      // Horizontal subdivisions
      ctx.moveTo(0, midY - 20); ctx.lineTo(sw, midY - 20);
      ctx.moveTo(0, midY + 20); ctx.lineTo(sw, midY + 20);
      ctx.stroke();

      // Plot Waveform Trace
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#00ffbc';
      ctx.shadowColor = 'rgba(0, 255, 188, 0.8)';
      ctx.shadowBlur = 8;

      if (state.micActive && state.analyserNode) {
        const sliceWidth = sw / timeData.length;
        let x = 0;
        for (let i = 0; i < timeData.length; i++) {
          const v = timeData[i] / 128.0;
          const y = v * (sh / 2);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
          x += sliceWidth;
        }
      } else {
        // Generate synthetic wave trace based on active pitch & oscillator
        state.synthPhase += 0.08;
        const amp = state.synthSimLevel * (sh * 0.38);
        const freqCycles = 4;

        for (let x = 0; x < sw; x++) {
          const t = (x / sw) * freqCycles * Math.PI * 2 + state.synthPhase;
          let wave = 0;
          if (state.params[20] > 60) {
            // Sawtooth
            wave = (2.0 * ((t / (Math.PI * 2)) % 1.0) - 1.0);
          } else if (state.params[19] > 60) {
            // Square / Pulse
            wave = Math.sin(t) > 0 ? 0.9 : -0.9;
          } else {
            // Triangle / sine
            wave = Math.sin(t);
          }
          const y = midY + wave * amp;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
      }

      ctx.stroke();
      ctx.shadowBlur = 0;
    }
  }

  requestAnimationFrame(renderFrame);
}

// --- 9. Acid 16-Step Sequencer ---
const ACID_SEQ = [
  { semi: 0,  len: 120, vel: 110 }, // C
  { semi: 0,  len: 100, vel: 90  }, // C
  { semi: 3,  len: 130, vel: 127 }, // D# (Accent)
  { semi: 0,  len: 100, vel: 90  }, // C
  { semi: 7,  len: 120, vel: 105 }, // G
  { semi: 5,  len: 110, vel: 95  }, // F
  { semi: 3,  len: 120, vel: 115 }, // D#
  { semi: 0,  len: 100, vel: 90  }, // C
  { semi: 12, len: 140, vel: 127 }, // C + 1 Oct (Accent)
  { semi: 10, len: 110, vel: 100 }, // A#
  { semi: 7,  len: 110, vel: 95  }, // G
  { semi: 6,  len: 100, vel: 90  }, // F#
  { semi: 5,  len: 110, vel: 95  }, // F
  { semi: 3,  len: 120, vel: 110 }, // D#
  { semi: 0,  len: 100, vel: 90  }, // C
  { semi: 10, len: 120, vel: 105 }  // A#
];

function toggleSequence() {
  const btn = document.getElementById('btnArpSeq');
  if (state.seqInterval) {
    stopSequence();
  } else {
    btn.classList.add('active');
    state.seqStep = 0;
    const stepTimeMs = 125; // 120 BPM 16th notes = 125ms

    state.seqInterval = setInterval(() => {
      const step = ACID_SEQ[state.seqStep];
      const baseNote = (state.octave * 12) + step.semi;

      sendNoteOn(baseNote, step.vel);
      highlightKey(step.semi, true);

      setTimeout(() => {
        sendNoteOff(baseNote);
        highlightKey(step.semi, false);
      }, step.len);

      state.seqStep = (state.seqStep + 1) % ACID_SEQ.length;
    }, stepTimeMs);

    showStatusAlert('PLAYING ACID 16-STEP SEQUENCE');
    logMidiEvent('SYS', 'ALL', 'SEQ', 'Acid 16-Step Sequencer started (120 BPM).', []);
  }
}

function stopSequence() {
  if (state.seqInterval) {
    clearInterval(state.seqInterval);
    state.seqInterval = null;
    const btn = document.getElementById('btnArpSeq');
    if (btn) btn.classList.remove('active');
    panicAllNotes();
    logMidiEvent('SYS', 'ALL', 'SEQ', 'Acid Sequencer stopped.', []);
  }
}

function highlightKey(semi, active) {
  const keyEl = document.querySelector(`.piano-keyboard [data-semi="${semi}"]`);
  if (keyEl) {
    keyEl.classList.toggle('active', active);
  }
}

// --- 10. Virtual 25-Key Piano Keyboard Generation ---
function buildPianoKeyboard() {
  const container = document.getElementById('pianoKeyboard');
  if (!container) return;
  container.innerHTML = '';

  const whiteKeys = KEY_DEFS.filter(k => !k.isBlack);
  const totalWhite = whiteKeys.length; // 15 white keys

  // Create White Keys
  let whiteIndex = 0;
  KEY_DEFS.forEach(k => {
    if (!k.isBlack) {
      const keyEl = document.createElement('div');
      keyEl.className = 'key-white';
      keyEl.setAttribute('data-semi', k.semi);
      keyEl.innerHTML = `<span class="key-label">${k.name} [${k.keyChar}]</span>`;
      attachKeyListeners(keyEl, k.semi);
      container.appendChild(keyEl);
      whiteIndex++;
    }
  });

  // Black key offsets relative to 15 white keys
  const blackKeyOffsets = [
    { semi: 1,  whiteIdx: 0 }, // C#
    { semi: 3,  whiteIdx: 1 }, // D#
    { semi: 6,  whiteIdx: 3 }, // F#
    { semi: 8,  whiteIdx: 4 }, // G#
    { semi: 10, whiteIdx: 5 }, // A#
    { semi: 13, whiteIdx: 7 }, // C#
    { semi: 15, whiteIdx: 8 }, // D#
    { semi: 18, whiteIdx: 10 },// F#
    { semi: 20, whiteIdx: 11 },// G#
    { semi: 22, whiteIdx: 12 } // A#
  ];

  const whiteKeyWidthPercent = 100.0 / totalWhite; // ~6.666%

  blackKeyOffsets.forEach(bk => {
    const def = KEY_DEFS.find(k => k.semi === bk.semi);
    const keyEl = document.createElement('div');
    keyEl.className = 'key-black';
    keyEl.setAttribute('data-semi', bk.semi);
    const leftPercent = (bk.whiteIdx + 1) * whiteKeyWidthPercent - 2.4;
    keyEl.style.left = `${leftPercent}%`;
    keyEl.innerHTML = `<span class="key-label">${def.keyChar}</span>`;
    attachKeyListeners(keyEl, bk.semi);
    container.appendChild(keyEl);
  });
}

function attachKeyListeners(keyEl, semi) {
  const triggerOn = (e) => {
    e.preventDefault();
    const note = (state.octave * 12) + semi;

    if (state.isLatched) {
      if (state.latchedNotes.has(note)) {
        state.latchedNotes.delete(note);
        sendNoteOff(note);
        keyEl.classList.remove('active');
      } else {
        state.latchedNotes.add(note);
        sendNoteOn(note, state.velocity);
        keyEl.classList.add('active');
      }
    } else {
      sendNoteOn(note, state.velocity);
      keyEl.classList.add('active');
    }
    updateActiveNoteDisplay(getNoteNameWithOctave(note));
  };

  const triggerOff = (e) => {
    e.preventDefault();
    if (!state.isLatched) {
      const note = (state.octave * 12) + semi;
      sendNoteOff(note);
      keyEl.classList.remove('active');
    }
  };

  keyEl.addEventListener('mousedown', triggerOn);
  keyEl.addEventListener('mouseup', triggerOff);
  keyEl.addEventListener('mouseleave', triggerOff);

  keyEl.addEventListener('touchstart', triggerOn, { passive: false });
  keyEl.addEventListener('touchend', triggerOff, { passive: false });
}

function getNoteNameWithOctave(note) {
  const name = NOTE_NAMES[note % 12];
  const oct = Math.floor(note / 12) - 1;
  return `${name}${oct} (MIDI ${note})`;
}

function updateActiveNoteDisplay(text) {
  const el = document.querySelector('#dispActiveNote .note-name');
  if (el) el.textContent = text;
}

// --- 11. Computer Keyboard Mapping ---
function setupComputerKeyboard() {
  const keyMap = {};
  KEY_DEFS.forEach(k => {
    keyMap[k.keyChar.toLowerCase()] = k.semi;
  });
  // Extra lower-row extension for single-row continuous playing
  keyMap[','] = 12; // C (Oct 2)
  keyMap['l'] = 13; // C#
  keyMap['.'] = 14; // D
  keyMap[';'] = 15; // D#
  keyMap['/'] = 16; // E

  const pressedKeys = new Set();

  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

    // Octave Shift Shortcuts: [ (down) and ] (up)
    if (e.key === '[' || e.code === 'BracketLeft') {
      if (state.octave > 1) {
        state.octave--;
        const disp = document.getElementById('dispOct');
        if (disp) disp.textContent = `OCT ${state.octave}`;
        showStatusAlert(`OCTAVE: ${state.octave}`);
      }
      return;
    }
    if (e.key === ']' || e.code === 'BracketRight') {
      if (state.octave < 8) {
        state.octave++;
        const disp = document.getElementById('dispOct');
        if (disp) disp.textContent = `OCT ${state.octave}`;
        showStatusAlert(`OCTAVE: ${state.octave}`);
      }
      return;
    }

    // Velocity Shortcuts: - (vel down) and = (vel up)
    if (e.key === '-' || e.code === 'Minus') {
      state.velocity = Math.max(10, state.velocity - 15);
      const sl = document.getElementById('slVelocity');
      const disp = document.getElementById('dispVel');
      if (sl) sl.value = state.velocity;
      if (disp) disp.textContent = state.velocity;
      showStatusAlert(`VELOCITY: ${state.velocity}`);
      return;
    }
    if (e.key === '=' || e.code === 'Equal') {
      state.velocity = Math.min(127, state.velocity + 15);
      const sl = document.getElementById('slVelocity');
      const disp = document.getElementById('dispVel');
      if (sl) sl.value = state.velocity;
      if (disp) disp.textContent = state.velocity;
      showStatusAlert(`VELOCITY: ${state.velocity}`);
      return;
    }

    const k = e.key.toLowerCase();
    if (keyMap[k] !== undefined && !pressedKeys.has(k)) {
      pressedKeys.add(k);
      const semi = keyMap[k];
      const note = (state.octave * 12) + semi;
      sendNoteOn(note, state.velocity);
      highlightKey(semi, true);
      updateActiveNoteDisplay(getNoteNameWithOctave(note));
    }
  });

  window.addEventListener('keyup', (e) => {
    const k = e.key.toLowerCase();
    if (keyMap[k] !== undefined) {
      pressedKeys.delete(k);
      const semi = keyMap[k];
      const note = (state.octave * 12) + semi;
      if (!state.isLatched) {
        sendNoteOff(note);
        highlightKey(semi, false);
      }
    }
  });
}

// --- 12. Bottom Toolbar & Octave Controls ---
function setupToolbar() {
  const dispOct = document.getElementById('dispOct');
  document.getElementById('btnOctDown')?.addEventListener('click', () => {
    if (state.octave > 1) {
      state.octave--;
      dispOct.textContent = `OCT ${state.octave}`;
    }
  });
  document.getElementById('btnOctUp')?.addEventListener('click', () => {
    if (state.octave < 8) {
      state.octave++;
      dispOct.textContent = `OCT ${state.octave}`;
    }
  });

  // Hold Note (Latch)
  const btnLatch = document.getElementById('btnLatch');
  if (btnLatch) {
    btnLatch.addEventListener('click', () => {
      state.isLatched = !state.isLatched;
      btnLatch.classList.toggle('active', state.isLatched);
      if (!state.isLatched) {
        panicAllNotes();
      }
    });
  }

  // Acid Sequence
  document.getElementById('btnArpSeq')?.addEventListener('click', toggleSequence);

  // Velocity slider
  const slVel = document.getElementById('slVelocity');
  const dispVel = document.getElementById('dispVel');
  if (slVel && dispVel) {
    slVel.addEventListener('input', () => {
      state.velocity = parseInt(slVel.value, 10);
      dispVel.textContent = state.velocity;
    });
  }

  // Target Destination Buttons
  document.getElementById('btnBoth')?.addEventListener('click', () => setTarget('both'));
  document.getElementById('btnS1')?.addEventListener('click', () => setTarget('s1'));
  document.getElementById('btnFM1')?.addEventListener('click', () => setTarget('fm1'));
  document.getElementById('btnABToggle')?.addEventListener('click', toggleAB);

  // Master Tempo slider
  const slTempo = document.getElementById('slTempo');
  const valTempo = document.getElementById('valTempo');
  if (slTempo && valTempo) {
    slTempo.addEventListener('input', () => {
      const bpm = parseInt(slTempo.value, 10);
      valTempo.textContent = `${bpm} BPM`;
      state.arp.tempo = bpm;
      sendCC(115, bpm);
      logMidiEvent('SYS', 'ALL', 'CLOCK', `Master Tempo set to ${bpm} BPM (CC 115)`, []);
    });
  }

  // MIDI port dropdown overrides
  document.getElementById('selS1Out')?.addEventListener('change', (e) => {
    const id = e.target.value;
    state.s1Out = state.midiOutputs.find(p => p.id === id) || null;
    updateIndicators();
  });
  document.getElementById('selFM1Out')?.addEventListener('change', (e) => {
    const id = e.target.value;
    state.fm1Out = state.midiOutputs.find(p => p.id === id) || null;
    updateIndicators();
  });
  document.getElementById('selMidiIn')?.addEventListener('change', (e) => {
    setMidiInput(e.target.value);
  });
}

// --- 13. Step Matrix (16-Step Wavetable Draw & 16-Step Chop Comb Mask) ---
function setupStepMatrix() {
  const drawGrid = document.getElementById('drawStepsGrid');
  const chopGrid = document.getElementById('chopPadsGrid');

  if (!state.drawSteps) {
    state.drawSteps = new Array(16).fill(0);
  }
  if (state.chopMask === undefined) {
    state.chopMask = 0xFFFF; // All 16 steps active
  }

  // 1. Build 16 Draw Step Faders (-100 to +100)
  if (drawGrid) {
    drawGrid.innerHTML = '';
    for (let i = 0; i < 16; i++) {
      const col = document.createElement('div');
      col.className = 'draw-step-col';
      col.innerHTML = `
        <span class="step-num">${i + 1}</span>
        <input type="range" class="slider draw-step-slider" min="-100" max="100" value="${state.drawSteps[i]}" data-step="${i}">
        <span class="step-val" id="valDrawStep${i}">${state.drawSteps[i]}</span>
      `;
      const slider = col.querySelector('.draw-step-slider');
      const valDisp = col.querySelector('.step-val');
      slider.addEventListener('input', () => {
        const v = parseInt(slider.value, 10);
        state.drawSteps[i] = v;
        valDisp.textContent = v;
        logMidiEvent('OUT', state.activeTarget, 'DRAW', `Step ${i + 1} Amplitude: ${v}`, []);
      });
      drawGrid.appendChild(col);
    }
  }

  // Draw Presets
  const updateDrawGridUI = () => {
    for (let i = 0; i < 16; i++) {
      const slider = drawGrid?.querySelector(`[data-step="${i}"]`);
      const valDisp = document.getElementById(`valDrawStep${i}`);
      if (slider) slider.value = state.drawSteps[i];
      if (valDisp) valDisp.textContent = state.drawSteps[i];
    }
    logMidiEvent('OUT', state.activeTarget, 'DRAW', `Updated 16 Draw Steps`, []);
  };

  document.getElementById('btnDrawSine')?.addEventListener('click', () => {
    for (let i = 0; i < 16; i++) {
      state.drawSteps[i] = Math.round(Math.sin((i / 16) * Math.PI * 2) * 100);
    }
    updateDrawGridUI();
  });

  document.getElementById('btnDrawTri')?.addEventListener('click', () => {
    for (let i = 0; i < 16; i++) {
      const phase = i / 16;
      state.drawSteps[i] = phase < 0.5 ? Math.round((phase * 4 - 1) * 100) : Math.round((3 - phase * 4) * 100);
    }
    updateDrawGridUI();
  });

  document.getElementById('btnDrawRamp')?.addEventListener('click', () => {
    for (let i = 0; i < 16; i++) {
      state.drawSteps[i] = Math.round(((i / 15) * 2 - 1) * 100);
    }
    updateDrawGridUI();
  });

  document.getElementById('btnDrawPulse')?.addEventListener('click', () => {
    for (let i = 0; i < 16; i++) {
      state.drawSteps[i] = i < 8 ? 100 : -100;
    }
    updateDrawGridUI();
  });

  document.getElementById('btnDrawRand')?.addEventListener('click', () => {
    for (let i = 0; i < 16; i++) {
      state.drawSteps[i] = Math.floor(Math.random() * 201) - 100;
    }
    updateDrawGridUI();
  });

  document.getElementById('btnDrawReset')?.addEventListener('click', () => {
    state.drawSteps.fill(0);
    updateDrawGridUI();
  });

  // 2. Build 16 Chop Pads
  if (chopGrid) {
    chopGrid.innerHTML = '';
    for (let i = 0; i < 16; i++) {
      const pad = document.createElement('button');
      const isActive = (state.chopMask & (1 << i)) !== 0;
      pad.className = `chop-pad-btn ${isActive ? 'active' : ''}`;
      pad.setAttribute('type', 'button');
      pad.setAttribute('data-pad', i);
      pad.innerHTML = `
        <span class="pad-num">${i + 1}</span>
        <span class="pad-led"></span>
      `;
      pad.addEventListener('click', () => {
        state.chopMask ^= (1 << i);
        const on = (state.chopMask & (1 << i)) !== 0;
        pad.classList.toggle('active', on);
        logMidiEvent('OUT', state.activeTarget, 'CHOP', `Chop Step ${i + 1} ${on ? 'ON' : 'OFF'} (Mask: 0x${state.chopMask.toString(16).toUpperCase()})`, []);
      });
      chopGrid.appendChild(pad);
    }
  }

  const updateChopPadsUI = () => {
    for (let i = 0; i < 16; i++) {
      const pad = chopGrid?.querySelector(`[data-pad="${i}"]`);
      if (pad) {
        const on = (state.chopMask & (1 << i)) !== 0;
        pad.classList.toggle('active', on);
      }
    }
    logMidiEvent('OUT', state.activeTarget, 'CHOP', `Chop Mask set to 0x${state.chopMask.toString(16).toUpperCase()}`, []);
  };

  document.getElementById('btnChopAllOn')?.addEventListener('click', () => {
    state.chopMask = 0xFFFF;
    updateChopPadsUI();
  });

  document.getElementById('btnChopEven')?.addEventListener('click', () => {
    state.chopMask = 0xAAAA; // Steps 2, 4, 6...
    updateChopPadsUI();
  });

  document.getElementById('btnChopOdd')?.addEventListener('click', () => {
    state.chopMask = 0x5555; // Steps 1, 3, 5...
    updateChopPadsUI();
  });

  document.getElementById('btnChopInvert')?.addEventListener('click', () => {
    state.chopMask = (~state.chopMask) & 0xFFFF;
    updateChopPadsUI();
  });
}

function showStatusAlert(msg) {
  const indicator = document.querySelector('#dispActiveNote .note-name');
  if (indicator) indicator.textContent = msg;
}

// --- 13. USB & Hardware Audio Routing (Synth Input -> Sound Card Pass-Through) ---
const audioRouter = {
  active: false,
  stream: null,
  sourceNode: null,
  analyserNode: null,
  gainNode: null,
  monitorVol: 1.0,     // 0.0 to 1.5
  s1Vol: 1.0,          // 0.0 to 1.5
  fm1Vol: 1.0,         // 0.0 to 1.5
  mode: 'both',        // 'both', 's1', 'fm1', 'mute'
  isMuted: false,
  selectedInputId: '',
  selectedOutputId: ''
};

async function populateAudioDevices() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  try {
    const devs = await navigator.mediaDevices.enumerateDevices();
    const selIn = document.getElementById('selAudioInput');
    const selOut = document.getElementById('selAudioSink');

    // 1. Audio Inputs (Synth / Mic / Line-In)
    if (selIn) {
      const currentIn = selIn.value || audioRouter.selectedInputId;
      selIn.innerHTML = '';
      const inputs = devs.filter(d => d.kind === 'audioinput');

      if (inputs.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Default Input (Mic / Line-In)';
        selIn.appendChild(opt);
      } else {
        inputs.forEach((d, idx) => {
          const opt = document.createElement('option');
          opt.value = d.deviceId;
          let label = d.label || `Audio Input ${idx + 1}`;
          if (/s-1|roland|fm-1|m-vave|felucca/i.test(label)) {
            label = `🎹 ${label}`;
          }
          opt.textContent = label;
          if (d.deviceId === currentIn || (!currentIn && /s-1|roland|fm-1|m-vave|felucca/i.test(label))) {
            opt.selected = true;
            audioRouter.selectedInputId = d.deviceId;
          }
          selIn.appendChild(opt);
        });
      }
    }

    // 2. Audio Outputs (Sound Cards / Headphones)
    if (selOut) {
      const currentOut = selOut.value || audioRouter.selectedOutputId;
      selOut.innerHTML = '';
      const outputs = devs.filter(d => d.kind === 'audiooutput');

      if (outputs.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Default Sound Card (Speakers / Headphones)';
        selOut.appendChild(opt);
      } else {
        outputs.forEach((d, idx) => {
          const opt = document.createElement('option');
          opt.value = d.deviceId;
          let label = d.label || `Sound Card Output ${idx + 1}`;
          if (/headphone|phones/i.test(label)) {
            label = `🎧 ${label}`;
          } else if (/speaker/i.test(label)) {
            label = `🔊 ${label}`;
          }
          opt.textContent = label;
          if (d.deviceId === currentOut) {
            opt.selected = true;
          }
          selOut.appendChild(opt);
        });
      }
    }
  } catch (err) {
    console.warn('Failed to enumerate audio devices:', err);
  }
}

async function startAudioRouting(inputId, outputId) {
  try {
    if (audioRouter.stream) {
      audioRouter.stream.getTracks().forEach(t => t.stop());
      audioRouter.stream = null;
    }
    if (audioRouter.sourceNode) {
      try { audioRouter.sourceNode.disconnect(); } catch (e) {}
      audioRouter.sourceNode = null;
    }

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!state.audioContext) {
      state.audioContext = new AudioCtx({ latencyHint: 'interactive' });
    }
    if (state.audioContext.state === 'suspended') {
      await state.audioContext.resume();
    }

    // Route audioContext output to chosen sound card sink
    if (outputId && typeof state.audioContext.setSinkId === 'function') {
      try {
        await state.audioContext.setSinkId(outputId);
      } catch (e) {
        console.warn('AudioContext.setSinkId failed:', e);
      }
    }

    // Capture raw, uncompressed synth audio without browser speech filtering
    const constraints = {
      audio: {
        deviceId: inputId ? { exact: inputId } : undefined,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        channelCount: 2,
        latency: 0
      }
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    audioRouter.stream = stream;
    state.micStream = stream;

    // Build Web Audio routing graph
    audioRouter.sourceNode = state.audioContext.createMediaStreamSource(stream);
    audioRouter.analyserNode = state.audioContext.createAnalyser();
    audioRouter.analyserNode.fftSize = 512;
    state.analyserNode = audioRouter.analyserNode;

    if (!audioRouter.gainNode) {
      audioRouter.gainNode = state.audioContext.createGain();
    }
    updateAudioGains();

    // CONNECT SYNTH INPUT -> ANALYSER -> GAIN NODE -> USER'S SOUND CARD (DESTINATION)!
    audioRouter.sourceNode.connect(audioRouter.analyserNode);
    audioRouter.analyserNode.connect(audioRouter.gainNode);
    audioRouter.gainNode.connect(state.audioContext.destination);

    audioRouter.active = true;
    state.micActive = true;

    // Refresh devices with actual human-readable labels now that mic permission is given
    await populateAudioDevices();

    updateAudioUIState(true);
    logMidiEvent('SYS', 'HOST', 'AUDIO', 'Hardware Synth Audio Input redirected to Sound Card Output.', []);
    showStatusAlert('AUDIO ROUTED: SYNTH ➔ SOUND CARD');
  } catch (err) {
    console.warn('Audio routing start error:', err);
    updateAudioUIState(false);
    showStatusAlert(`Audio Input error: ${err.message}`);
    logMidiEvent('SYS', 'HOST', 'AUDIO', `Audio routing error: ${err.message}`, []);
  }
}

function stopAudioRouting() {
  if (audioRouter.stream) {
    audioRouter.stream.getTracks().forEach(t => t.stop());
    audioRouter.stream = null;
    state.micStream = null;
  }
  if (audioRouter.sourceNode) {
    try { audioRouter.sourceNode.disconnect(); } catch (e) {}
    audioRouter.sourceNode = null;
  }
  audioRouter.active = false;
  state.micActive = false;
  updateAudioUIState(false);
  logMidiEvent('SYS', 'HOST', 'AUDIO', 'Audio pass-through stopped.', []);
  showStatusAlert('AUDIO PASS-THROUGH STOPPED');
}

function toggleAudioRouting() {
  if (audioRouter.active) {
    stopAudioRouting();
  } else {
    startAudioRouting(audioRouter.selectedInputId, audioRouter.selectedOutputId);
  }
}

function updateAudioUIState(active) {
  const btnPass = document.getElementById('btnAudioPassthrough');
  const txtPass = document.getElementById('txtAudioPassthrough');
  const btnMic = document.getElementById('btnAudioInput');
  const scopeStatus = document.getElementById('scopeStatus');

  if (btnPass) btnPass.classList.toggle('active', active);
  if (txtPass) txtPass.textContent = active ? 'HEAR SYNTH: LIVE (ROUTED TO SOUND CARD)' : 'HEAR SYNTH: OFF (CLICK TO LISTEN)';
  if (btnMic) {
    btnMic.classList.toggle('active', active);
    btnMic.textContent = active ? 'DISABLE MIC/LINE IN' : 'ENABLE MIC/LINE IN';
  }
  if (scopeStatus) {
    scopeStatus.textContent = active ? 'LIVE HARDWARE (PASS-THROUGH ON)' : 'SYNTH PREVIEW';
  }
}

function updateAudioGains() {
  if (!audioRouter.gainNode || !state.audioContext) return;
  let targetGain = 0;
  if (!audioRouter.isMuted) {
    let scale = 1.0;
    if (audioRouter.mode === 's1') scale = audioRouter.s1Vol;
    else if (audioRouter.mode === 'fm1') scale = audioRouter.fm1Vol;
    else scale = Math.max(audioRouter.s1Vol, audioRouter.fm1Vol);
    targetGain = audioRouter.monitorVol * scale;
  }
  audioRouter.gainNode.gain.setTargetAtTime(targetGain, state.audioContext.currentTime, 0.02);
}

function setAudioMode(mode) {
  audioRouter.mode = mode;
  audioRouter.isMuted = (mode === 'mute');
  updateAudioGains();
  updateAudioModeUI(mode);

  // Notify server for PipeWire compatibility on Linux
  fetch('/api/audio/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  }).catch(() => {});
}

function updateAudioModeUI(mode) {
  document.querySelectorAll('.audio-mode-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-mode') === mode);
  });
}

async function initAudioMonitor() {
  if (!document.getElementById('selAudioInput')) return;
  // 1. Initial device population
  await populateAudioDevices();

  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener('devicechange', () => {
      populateAudioDevices();
    });
  }

  // 2. Wire Pass-Through Toggle Button
  const btnPass = document.getElementById('btnAudioPassthrough');
  if (btnPass) {
    btnPass.addEventListener('click', toggleAudioRouting);
  }

  // 3. Wire Device Selection Dropdowns
  const selIn = document.getElementById('selAudioInput');
  if (selIn) {
    selIn.addEventListener('change', () => {
      audioRouter.selectedInputId = selIn.value;
      if (audioRouter.active) {
        startAudioRouting(audioRouter.selectedInputId, audioRouter.selectedOutputId);
      }
    });
  }

  const selOut = document.getElementById('selAudioSink');
  if (selOut) {
    selOut.addEventListener('change', async () => {
      audioRouter.selectedOutputId = selOut.value;
      if (state.audioContext && typeof state.audioContext.setSinkId === 'function') {
        try {
          await state.audioContext.setSinkId(selOut.value);
        } catch (e) {
          console.warn('AudioContext.setSinkId failed:', e);
        }
      }
      fetch('/api/audio/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: audioRouter.mode, sink: selOut.value })
      }).catch(() => {});
    });
  }

  // 4. Wire Audio Mode Buttons (Both, Solo S-1, Solo FM-1, Mute)
  document.querySelectorAll('.audio-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      setAudioMode(mode);
    });
  });

  // 5. Wire Volume Sliders
  const slMon = document.getElementById('slMonitorVol');
  const dispMon = document.getElementById('dispMonitorVol');
  if (slMon && dispMon) {
    slMon.addEventListener('input', () => {
      const val = parseInt(slMon.value, 10);
      dispMon.textContent = `${val}%`;
      audioRouter.monitorVol = val / 100.0;
      updateAudioGains();
    });
  }

  const slS1 = document.getElementById('slS1AudioVol');
  const dispS1 = document.getElementById('dispS1Vol');
  if (slS1 && dispS1) {
    slS1.addEventListener('input', () => {
      const val = parseInt(slS1.value, 10);
      dispS1.textContent = `${val}%`;
      audioRouter.s1Vol = val / 100.0;
      updateAudioGains();
      fetch('/api/audio/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device: 's1', volume: val / 100.0 })
      }).catch(() => {});
    });
  }

  const slFM1 = document.getElementById('slFM1AudioVol');
  const dispFM1 = document.getElementById('dispFM1Vol');
  if (slFM1 && dispFM1) {
    slFM1.addEventListener('input', () => {
      const val = parseInt(slFM1.value, 10);
      dispFM1.textContent = `${val}%`;
      audioRouter.fm1Vol = val / 100.0;
      updateAudioGains();
      fetch('/api/audio/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device: 'fm1', volume: val / 100.0 })
      }).catch(() => {});
    });
  }

  // 6. Query server for initial Linux audio status if available
  try {
    const res = await fetch('/api/audio');
    if (res.ok) {
      const data = await res.json();
      if (data.mode) updateAudioModeUI(data.mode);
      if (data.s1 && data.s1.volume !== undefined && slS1 && dispS1) {
        const pct = Math.round(data.s1.volume * 100);
        slS1.value = pct;
        dispS1.textContent = `${pct}%`;
        audioRouter.s1Vol = data.s1.volume;
      }
      if (data.fm1 && data.fm1.volume !== undefined && slFM1 && dispFM1) {
        const pct = Math.round(data.fm1.volume * 100);
        slFM1.value = pct;
        dispFM1.textContent = `${pct}%`;
        audioRouter.fm1Vol = data.fm1.volume;
      }
    }
  } catch (e) {
    // Standalone / offline mode
  }
}

// --- 14. Bootstrap Everything on DOM Ready ---
window.addEventListener('DOMContentLoaded', () => {
  buildPianoKeyboard();
  setupSliders();
  setupButtonGroups();
  setupStepMatrix();
  setupPatchToolbar();
  setupMidiLogControls();
  setupToolbar();
  setupComputerKeyboard();
  setupAudioInput();
  drawEnvCurve();
  startVisualizerLoop();
  initPresetDropdown();
  initMIDI();
  initAudioMonitor();
});
