# UI Overhaul Design — DAW-Inspired Editor Layout

## Context
The editor view has UX issues: instrument selector is far from synthesize, Play defaults to synthesized audio confusingly, the notes table duplicates piano roll functionality, and the vertical card-stack layout wastes space. This overhaul creates a compact DAW-inspired layout with A/B playback.

## Design

### Top Control Bar (replaces toolbar + instrument card + track selector)
Single card, two rows:

**Row 1 — Transport:**
```
Track: [dropdown▾]  │  ▶  ⏸  ⏹  │  ◉ Original  ○ Synth  │  🔊 Region
```
- Source toggle: segmented control, radio-style. "Synth" disabled until synthesized.
- Play/Pause/Stop always uses the selected source (original or synth audio).
- "Play Region" plays selected region using the active source. Disabled when no region.
- After Synthesize completes, auto-switch source to "Synth".

**Row 2 — Actions:**
```
Instrument: [Piano▾]  │  [Extract MIDI]  [Synthesize]
```
- Instrument dropdown right next to Synthesize.
- Extract MIDI starts the MIDI extraction pipeline.

### Waveform + Piano Roll (unified visual block)
- Remove individual card wrappers and section headers.
- Waveform sits directly above piano roll with only a 1px divider.
- They share the same horizontal time axis visually.
- Wrap both in a single container with shared styling.

### Remove Notes Table
- Piano roll IS the note editor (drag, create, delete, resize).
- Note count displayed in status bar.
- Removes ~80 lines of table rendering code.

### Status Bar (bottom)
Three segments in a flex row:
```
Ready  │  Region: 1.20s — 3.50s  │  42 notes
```

### CSS Changes
- Max-width: 1200px → 1400px
- Control bar: flex rows with gap, aligned groups
- Segmented control: pill-shaped toggle for Original/Synth
- Waveform+piano roll: no card padding, seamless vertical stacking
- Button groups: subtle borders between groups, not separate cards
- Disabled states: opacity + cursor changes

## Files to Modify
- `frontend/src/components/waveform.ts` — major rewrite of renderEditorView
- `frontend/src/components/toolbar.ts` — rewrite with new layout + source toggle + region play
- `frontend/src/styles/main.css` — new control-bar, segmented-control, status-bar styles
- `frontend/src/main.ts` — no changes needed

## Files to Delete
- None (notes table code is inline in waveform.ts, just remove it)

## Playback Logic Change
Current: WaveSurfer loads original, then replaces with synth URL after synthesize.
New: Track both URLs in state. WaveSurfer loads whichever source is active. Toggle switches WaveSurfer URL.

## Verification
1. `npm run build` — no TS errors
2. `npm test` — all tests pass (update toolbar tests for new interface)
3. Manual: upload track → extract → edit in piano roll → synthesize → toggle Original/Synth → play region
