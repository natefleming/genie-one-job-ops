---
name: Genie One Job Ops
description: One Genie One conversation about a 2 a.m. failure, set in the Databricks oat, navy and lava visual language.
colors:
  lava: "#FF3621"
  lava-soft: "#FFE3DE"
  lava-deep: "#9A1D0D"
  navy: "#1B3139"
  ink: "#0B2026"
  teal: "#1B5162"
  muted-teal: "#4A6B77"
  oat: "#F9F7F4"
  oat-2: "#EEEDE9"
  oat-3: "#DBD7CE"
  line: "#E2DED5"
  white: "#FFFFFF"
  navy-raised: "#233F48"
  navy-rule: "#35505A"
  mist: "#9FB6BD"
  mist-light: "#CFDDE1"
  coral-key: "#FFB4A8"
  green-soft: "#DDF3EA"
  green-deep: "#00663F"
  amber-soft: "#FFF1D1"
  amber-deep: "#7A4F00"
typography:
  display:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "96px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  headline-small:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "46px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  title:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    letterSpacing: "-0.015em"
  body:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 400
    lineHeight: 1.38
  lede:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 500
  note:
    fontFamily: "DM Sans, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 400
  mono:
    fontFamily: "DM Mono, ui-monospace, monospace"
    fontSize: "20px"
    fontWeight: 400
    letterSpacing: "0.02em"
rounded:
  code: "10px"
  button: "12px"
  layer: "18px"
  card-dark: "22px"
  panel: "24px"
  bubble: "36px"
  pill: "999px"
spacing:
  chip-gap: "12px"
  card-gap: "34px"
  column-gap: "64px"
  canvas-top: "110px"
  canvas-side: "120px"
  canvas-bottom: "130px"
components:
  ask-bubble:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.oat}"
    typography: "{typography.headline-small}"
    padding: "20px 36px 24px"
  ask-bubble-dark:
    backgroundColor: "{colors.oat}"
    textColor: "{colors.navy}"
    typography: "{typography.headline-small}"
  answer-card:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "40px 48px"
  answer-card-dark:
    backgroundColor: "{colors.navy-raised}"
    textColor: "{colors.oat}"
  button-outline:
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "12px 22px"
  button-commit:
    backgroundColor: "{colors.lava}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "12px 22px"
  chip:
    backgroundColor: "{colors.oat-2}"
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "9px 18px"
  chip-data:
    backgroundColor: "{colors.lava-soft}"
    textColor: "{colors.lava-deep}"
    rounded: "{rounded.pill}"
  chip-ok:
    backgroundColor: "{colors.green-soft}"
    textColor: "{colors.green-deep}"
    rounded: "{rounded.pill}"
  chip-warn:
    backgroundColor: "{colors.amber-soft}"
    textColor: "{colors.amber-deep}"
    rounded: "{rounded.pill}"
  layer-row:
    backgroundColor: "{colors.navy-raised}"
    textColor: "{colors.white}"
    rounded: "{rounded.layer}"
    padding: "22px 30px"
---

# Design System: Genie One Job Ops

## Overview

**Creative North Star: "The 2 a.m. Thread"**

The deck is one Genie One conversation. Each slide is a question and its answer: a navy question bubble, then a white answer card set on warm Databricks oat paper. Composition comes from the conversation itself. Questions pin to one side, answers hang below them, and a thin four-station rail along the foot (Ask, Understand, Impact, Fix) shows how far the story has got. The answer card is where the reading happens. Lava marks the one thing in it that matters and nothing else.

The deck has two registers. The light oat register tells the incident story, slides 1 to 7 on the rail. The dark navy "under the hood" register explains the build, and there the bubble turns oat and the cards turn raised navy. Afterwards the surfaces return to oat with the rail removed. Everything sits on a fixed 1920 × 1080 canvas scaled to the window and exported to PDF at the same size, so the deck is dense but large: body copy is 34px and nothing a reader needs falls below 20px.

Motion is a single gesture. Each answer types in word by word once, the first time its slide is entered. Revisits, PDF export and reduced-motion all show the finished text immediately.

**Key Characteristics:**
- Oat paper ground, navy ink, lava as the single focus accent
- Question bubble / answer card pairs with asymmetric "tail" corners
- Four-station rail on story slides, with Fix as the lava commit point
- Light story register and a dark navy build register
- DM Sans for all text; DM Mono only for clocks, page numbers, object names and code
- Soft, low, navy-tinted ambient shadows; no hard edges

## Colors

A warm-paper Databricks palette: oat neutrals, navy-teal ink, one hot lava accent, and three quiet status tints.

### Primary
- **Lava** (#FF3621): the one thing that matters. Use it for the highlighted phrase in an answer (bold lava text), the commit button (Open in Genie ZeroOps), the Fix station when lit, the current step node in a timeline, the commit path's 4px top rule, the Genie spark mark, and list check icons. **Lava Soft** (#FFE3DE) with **Lava Deep** (#9A1D0D) is the "Data error" chip and failed-row text. Lava Deep also colours error lines in code.

### Neutral
- **Oat** (#F9F7F4): the slide ground, the question-bubble fill on dark slides, and the highlighted Genie One layer on the big-picture slide.
- **Oat 2** (#EEEDE9): default chip and pill fill on light surfaces.
- **Oat 3** (#DBD7CE): rail segments and timeline connectors.
- **Line** (#E2DED5): hairline row dividers, path top rules, screenshot borders.
- **White** (#FFFFFF): answer cards and compare panels.
- **Navy** (#1B3139): question-bubble fill, dark-slide ground, bold emphasis inside answers, button outline and text.
- **Ink** (#0B2026): answer body text and the source of every shadow tint.
- **Teal** (#1B5162): secondary prose such as ledes, path descriptions and table "why" cells.
- **Muted Teal** (#4A6B77): chrome on light slides (topbar, rail labels, Genie tag, notes, mono timestamps).
- **Navy Raised** (#233F48): cards, layer rows and the skill card on dark slides.
- **Navy Rule** (#35505A): rail and connector lines on dark slides.
- **Mist** (#9FB6BD) and **Mist Light** (#CFDDE1): chrome and body text on dark slides. **Coral Key** (#FFB4A8) colours field keys inside the mono skill card.

### Status tints
- **Green Soft / Green Deep** (#DDF3EA / #00663F): healthy or "loaded" chips and diagram nodes.
- **Amber Soft / Amber Deep** (#FFF1D1 / #7A4F00): upstream or waiting chips ("Upstream: MuleSoft").

### Named Rules
**The One Thing Rule.** An answer gets at most one lava phrase, and a slide gets one lava action. Lava says "this one", so two lava marks compete.

**The Fix Is Lava Rule.** On the rail, Ask, Understand and Impact light in navy (oat on dark). Only Fix lights in lava, and its dot is larger (18px against 14px). The commit point is the only stop that shares the accent.

## Typography

**Display Font:** DM Sans (with system-ui, sans-serif), optical sizing 9..40, weights 400 to 700
**Label/Mono Font:** DM Mono (with ui-monospace), weights 400 and 500

**Character:** One friendly, slightly geometric sans carries the whole conversation, tight and heavy in the bubbles and open in the answers. Mono is a reading cue, not decoration: it marks machine facts such as clock times, page counts, table names and skill text.

### Hierarchy
- **Display** (600, 96px, 1.08, -0.025em): the title-slide question only.
- **Headline** (600, 64px, 1.08, -0.025em): a full-size question bubble that opens or closes a section.
- **Headline Small** (600, 46px, 1.08, -0.025em): the standard question bubble on most slides.
- **Title** (700, 26 to 36px, -0.015em): in-card subheads such as path names, step names and compare headers.
- **Body** (400, 34px, 1.38): answer-card text, with bold navy for named objects. Lists and tables step down to 27 or 28px.
- **Lede** (400, 30px, 1.45, max about 1300px): explanatory prose under a bubble, in teal.
- **Label** (500, 22px): chips, buttons, the topbar.
- **Note** (400, 20px): provenance and caveat lines in muted teal ("From the working build in our demo workspace…").
- **Mono** (400, 18 to 26px, +0.02em): clocks, page numbers, scramble timestamps, code lines, the skill card.

### Named Rules
**The Machine Facts Rule.** DM Mono is only for things a machine wrote or counts: timestamps, run and table names, skill source, page numbers. Prose never uses it.

**The 20px Floor Rule.** On the 1920 canvas, readable text stays at 20px or more. Mono page numbers at 18px are the only smaller element.

## Layout

The deck is a fixed 1920 × 1080 canvas scaled uniformly to the viewport, with no responsive reflow. Each slide is a vertically centred flex column inside 110px top, 120px side and 130px bottom padding. Chrome sits outside that column. The topbar (spark mark plus mono clock) is pinned 44px from the top. The rail, or the page number on slides without a rail, is pinned 52px from the bottom. Both are inset 120px from the sides.

The conversation sets the alignment. A question bubble sits in a row aligned right by default, or left on title and section-opening slides, and its answer card follows 30 to 46px below. Two-up content uses an equal two-column grid with a 64px gap (bubble and lede on one side, diagram or card on the other). Inside cards, chips wrap with a 12px gap and stacked blocks use a 34px gap. Five-step timelines use five equal columns joined by a 3px connector behind 46px circular nodes.

**The Clock Advances Rule.** Each slide's topbar clock moves forward in mono (02:14, 06:02, 06:03…), so the thread reads as one night unfolding.

## Elevation & Depth

Light slides use soft ambient lift. Dark slides are flat and use tonal layering. Every shadow is tinted with Ink, spread negatively so it pools under the element rather than haloing around it, and never offset hard. On dark slides, depth comes only from Navy Raised against Navy.

### Shadow Vocabulary
- **Bubble lift** (`box-shadow: 0 18px 40px -22px rgb(11 32 38 / 0.55)`): under question bubbles.
- **Card float** (`box-shadow: 0 30px 60px -36px rgb(11 32 38 / 0.35), 0 1px 0 #E2DED5`): under answer cards on oat.
- **Artifact drop** (`box-shadow: 0 40px 80px -40px rgb(11 32 38 / 0.55)`): screenshots and the phone mock.

### Named Rules
**The Flat Under The Hood Rule.** Dark slides carry no shadows. Raised navy surfaces separate by tone alone.

## Shapes

The shapes are rounded and conversational. The defining move is the speech-bubble tail done with one tight corner. The question bubble is rounded 36px on three corners and 10px on the bottom-right, the corner nearest the speaker. The answer card is 10px top-left and 36px elsewhere, so it hangs from the question. Chips and pills are full capsules (999px). Buttons are gently squared (12px) with a 2px border. Layer rows are 18px, dark skill cards 22px, compare panels 24px, code lines 10px. Rail and timeline nodes are circles, outlined when idle and filled when current. Rules are hairlines (1px Line) except on the commit path (4px lava top border) and timeline connectors (2 to 3px).

## Components

### Question Bubble
The question bubble is the speaker, heavy and dark. It uses Navy fill, Oat text, Headline Small (or Headline / Display at section and title scale), 20px 36px 24px padding (26px 44px 30px at full size), the asymmetric tail radius and bubble lift. On dark slides it inverts to an Oat fill with Navy text.

### Answer Card
The answer card is the reply, open and white. It uses a White fill, Ink body at 34px / 1.38, 40px 48px padding, the hanging-tail radius and card float. It opens with a Genie tag: a 22px lava spark and "Genie One · Job Ops" at 20px muted teal, with a source suffix when it matters ("from Unity Catalog lineage"). Named objects are bold Navy and the one key phrase is bold Lava. On dark slides it uses Navy Raised with no shadow.

### Buttons
- **Shape:** gently squared (12px), 2px border, 12px 22px padding, Label type, with a 20px inline SVG icon before the text.
- **Outline (default):** Navy border and text on a transparent fill, for "Open the run" and "Repair in Databricks".
- **Commit:** Lava fill and border with White text, used only for the ZeroOps path.
- These are static presentation affordances. Links are inert, so there is no hover vocabulary.

### Chips
- **Style:** capsule, 9px 18px padding, 22px weight 500, with an optional 20px SVG icon.
- **Variants:** neutral (Oat 2 / Navy), data error (Lava Soft / Lava Deep), ok (Green Soft / Green Deep), warn (Amber Soft / Amber Deep). On dark slides, pills use 10% oat over navy, and one lava pill (Ink text, bold) marks the fix.

### Station Rail
A 20px muted-teal row along the foot with four stops (Ask, Understand, Impact, Fix) joined by flexible 2px Oat 3 segments, followed by the mono page count. Stop dots are 14px outlined circles, and the current stop fills Navy with weight 600. Fix uses an 18px dot and turns Lava when lit. The rail is removed on slides with no station (the dark build slides and the closing slides), which show a bare mono page number instead.

### Layer Row (dark)
A two-column row (360px name, then pills) on Navy Raised with an 18px radius and 22px 30px padding. The name is 30px bold White. The row being described inverts to Oat with Navy text, so one layer reads as the subject.

### Typing Reveal
Answer text is split into words. Each word fades from opacity 0 and 4px blur to sharp over 0.28s on `cubic-bezier(.16,1,.3,1)`, staggered 38ms after a 120ms lead. It plays once per slide. Revisits, `prefers-reduced-motion` and PDF export show it settled.

## Do's and Don'ts

### Do:
- **Do** frame every content slide as a question bubble and its answer. The question is the slide title.
- **Do** keep lava to one phrase per answer and one action per slide, and make that action the fix or commit.
- **Do** light the rail stop for the slide's station and keep Fix as the only lava stop.
- **Do** use DM Mono for clocks, page numbers, object names and code, and DM Sans for everything else.
- **Do** inverse the bubble (Oat on Navy) and flatten the cards (Navy Raised, no shadow) on under-the-hood slides.
- **Do** tint every shadow with Ink and spread it negatively (for example `0 30px 60px -36px rgb(11 32 38 / 0.35)`).
- **Do** label demo data and roadmap items in a 20px muted-teal note under the card.
- **Do** draw icons as inline stroke SVG at 2 to 2.4px, coloured by `currentColor`.

### Don't:
- **Don't** use lava for decoration, backgrounds or more than one highlight in an answer.
- **Don't** set prose in DM Mono or use a second display face.
- **Don't** put shadows on dark slides or use hard offset shadows anywhere.
- **Don't** set reader-facing text below 20px on the 1920 canvas.
- **Don't** add uppercase kickers or eyebrows above the bubble. The question is the heading.
- **Don't** add a customer logo or brand assets. The visual language is Databricks-led.

## Related surface

The Job Ops web app (`app/frontend/src/styles.css`) is a separate, Operate-mode surface. It uses Inter, a lighter warm-grey ground (#F4F3F0) and the deck's Teal (#1B5162) as its accent, with light and dark schemes. It shares the Databricks lineage but not this deck's tokens. Do not treat this document as its system.
