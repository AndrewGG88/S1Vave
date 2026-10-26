// SPDX-License-Identifier: GPL-3.0-only
// S1Vave in an AudioWorklet: s1vave.wasm is the firmware (firmware/src, unchanged) on a simulated FM-1
// (web/sim/sim.c). Each 128-frame render quantum runs the device's clock: the ISR's 256-frame blocks are served out
// of sim_render, the main loop runs once per millisecond of it. ~30 times a second the screen (when it changed) and
// the LEDs go to the page; about once a second the storage, when a save changed it.
// After Makkuro37's web/sim/worklet.js (M. Geisler) and winampFM's sim/fm1-worklet.js (hericdk), GPL-3.0.
class S1Vave extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = options.processorOptions || {};
    this.ex = null;
    this.fbHash = -1;
    this.storeHash = 0;
    this.lastPost = 0;
    this.lastStore = 0;
    try {
      const mod = new WebAssembly.Module(o.wasm);
      this.ex = new WebAssembly.Instance(mod, {}).exports;
      const ex = this.ex, size = ex.sim_blob_size();
      if (o.store && o.store.byteLength === 9 * size) {     // the saved programs, settings and patterns, before boot
        const src = new Uint8Array(o.store);
        for (let i = 0; i < 9; i++) new Uint8Array(ex.memory.buffer, ex.sim_blob(i), size).set(src.subarray(i * size, (i + 1) * size));
      }
      if (ex.sim_init(44100) !== 0) throw new Error('sim_init failed');
      if (o.master !== undefined) ex.sim_master(o.master);
      this.storeHash = ex.sim_store_hash();
      this.port.postMessage({ t: 'ready' });
    } catch (err) {
      this.ex = null;
      this.port.postMessage({ t: 'error', message: String((err && err.message) || err) });
    }
    this.port.onmessage = (e) => this.onMessage(e.data);
  }
  onMessage(m) {
    const ex = this.ex;
    if (!ex) return;
    if (m.t === 'key') ex.sim_key(m.k, m.down ? 1 : 0);
    else if (m.t === 'btn') ex.sim_button(m.b, m.down ? 1 : 0);
    else if (m.t === 'enc') ex.sim_enc(m.e, m.steps | 0);
    else if (m.t === 'midi') ex.sim_midi(m.d[0] | 0, m.d[1] | 0, m.d[2] | 0);
    else if (m.t === 'master') ex.sim_master(m.v | 0);
  }
  publish() {
    const ex = this.ex, msg = { t: 'frame', leds: ex.sim_leds_buttons(), keys: ex.sim_leds_keys(), glow: ex.sim_glow_keys() }, tr = [];
    const h = ex.sim_fb_hash();
    if (h !== this.fbHash) {
      this.fbHash = h;
      msg.fb = new Uint16Array(ex.memory.buffer, ex.sim_fb(), 240 * 240).slice();
      tr.push(msg.fb.buffer);
    }
    this.port.postMessage(msg, tr);
  }
  saveStore() {
    const ex = this.ex, h = ex.sim_store_hash();
    if (h === this.storeHash) return;
    this.storeHash = h;
    const size = ex.sim_blob_size(), all = new Uint8Array(9 * size);
    for (let i = 0; i < 9; i++) all.set(new Uint8Array(ex.memory.buffer, ex.sim_blob(i), size), i * size);
    this.port.postMessage({ t: 'store', data: all.buffer }, [all.buffer]);
  }
  process(inputs, outputs) {
    const ex = this.ex;
    if (!ex) return true;
    const out = outputs[0], n = out[0].length;
    const sr = (typeof sampleRate !== 'undefined' && sampleRate) ? sampleRate : 44100;
    if (sr === 44100) {
      ex.sim_render(n);
      out[0].set(new Float32Array(ex.memory.buffer, ex.sim_out_l(), n));
      if (out[1]) out[1].set(new Float32Array(ex.memory.buffer, ex.sim_out_r(), n));
    } else {
      const ratio = 44100 / sr;
      const needed = Math.min(1024, Math.ceil(n * ratio) + 2);
      ex.sim_render(needed);
      const inL = new Float32Array(ex.memory.buffer, ex.sim_out_l(), needed);
      const inR = new Float32Array(ex.memory.buffer, ex.sim_out_r(), needed);
      const outL = out[0], outR = out[1];
      let p = this.resampPhase || 0;
      for (let i = 0; i < n; i++) {
        const idx = p | 0;
        const frac = p - idx;
        const l0 = idx === 0 ? (this.lastL !== undefined ? this.lastL : inL[0]) : inL[idx - 1];
        const l1 = inL[idx] !== undefined ? inL[idx] : l0;
        const r0 = idx === 0 ? (this.lastR !== undefined ? this.lastR : inR[0]) : inR[idx - 1];
        const r1 = inR[idx] !== undefined ? inR[idx] : r0;
        outL[i] = l0 + (l1 - l0) * frac;
        if (outR) outR[i] = r0 + (r1 - r0) * frac;
        p += ratio;
      }
      this.lastL = inL[needed - 1];
      this.lastR = inR[needed - 1];
      this.resampPhase = p - (needed - 1);
      if (this.resampPhase < 0) this.resampPhase = 0;
    }
    if (currentTime - this.lastPost >= 1 / 30) {
      this.lastPost = currentTime;
      this.publish();
    }
    if (currentTime - this.lastStore >= 1) {
      this.lastStore = currentTime;
      this.saveStore();
    }
    return true;
  }
}
registerProcessor('s1vave', S1Vave);
