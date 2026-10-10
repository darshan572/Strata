---
name: Raven Desktop
colors:
  surface: '#12121d'
  surface-dim: '#12121d'
  surface-bright: '#393844'
  surface-container-lowest: '#0d0d17'
  surface-container-low: '#1b1b25'
  surface-container: '#1f1f29'
  surface-container-high: '#292934'
  surface-container-highest: '#34343f'
  on-surface: '#e4e1f0'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#e3e0f1'
  inverse-on-surface: '#302f3b'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#e1dfff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#585990'
  secondary: '#fbabff'
  on-secondary: '#580065'
  secondary-container: '#ae05c6'
  on-secondary-container: '#ffd8fd'
  tertiary: '#acedff'
  on-tertiary: '#003640'
  tertiary-container: '#009eb9'
  on-tertiary-container: '#002f38'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#131449'
  on-primary-fixed-variant: '#404176'
  secondary-fixed: '#ffd6fd'
  secondary-fixed-dim: '#fbabff'
  on-secondary-fixed: '#36003e'
  on-secondary-fixed-variant: '#6d2b75'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#12121d'
  on-background: '#e3e0f1'
  surface-variant: '#343440'
  error-container-text: '#ffdad6'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.005em
  label-code-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
  label-code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.01em
  label-ui:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-desktop: 1rem
  margin: 0.75rem
  margin-desktop: 1.25rem
  space-xxs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 3rem
---

## Brand & Style

This design system establishes an architectural and spatial aesthetic engineered specifically for an advanced desktop browser. The design language fuses sculpted claymorphic physical surfaces with illuminated frosted glassmorphism, creating an atmospheric workspace that feels tangible, fluid, and computationally sovereign.

### Personality & Emotional Resonance
The experience balances deep technical precision with tactile serenity. Rather than flat, disposable web surfaces, components exhibit physical mass, subtle ambient glow, and micro-extruded depth. It evokes the feeling of interacting with a bespoke piece of high-precision computational hardware: calm, private, focused, and decisively modern.

### Aesthetic Framework: Tactile Clay-Glass Synthesis
The UI language merges two complementary material systems:
- **Sculptural Claymorphism:** Surface containers, active tabs, floating command palettes, and primary controls utilize dual-source illumination (diffused top-left ambient specular highlight paired with soft bottom-right occlusion shadows). Surfaces appear smooth, matte, and gently inflated rather than glossy or skeuomorphic.
- **Frosted Specular Glass:** Sidebars, pinned panels, URL omnibars, and webview overlays employ optical backdrop filtration (`backdrop-filter: blur(24px) saturate(160%)`) over dark midnight voids, punctuated by hairline inner specular borders.
- **Micro-Sensory Kinetic Response:** Interactive elements feature micro-spring animations with physical depression (inner inset depth shifting from convex to concave on press), reinforcing immediate mechanical feedback.

## Colors

The palette is tuned around midnight spectrum luminance, offering high contrast without optical fatigue. Pure black is avoided in favor of deep midnight indigo and charcoal basalt, allowing light to propagate through frosted volumes naturally.

### Palette Architecture

- **Canvas Base & Midnight Layers:** Deepest chrome frames, sidebar panels, and resting raised tiles use high-precision dark values to establish infinite depth.
- **Illumination & Accents:** Vibrant system focus states, creative workspaces, security warnings, and network transmission markers inject precise operational indicators.
- **Light Theme & Document Panels:** Off-white canvas and high-contrast ink support auxiliary reader mode panels and light modality palettes.

### Color Semantics & Optical Rules
1. **Never use non-tinted neutrals for borders:** All partition lines and glass rims must utilize variable alpha indigo tints.
2. **Radial Energy Leaks:** Primary and secondary accent colors should be deployed as low-opacity radial gradients (ambient underglows) placed behind elevated surface controls rather than flat fill blankets.

## Typography

The typographic hierarchy separates structural navigation, general textual content, and runtime technical chrome into three deliberate type systems.

### Type Pairings
- **Display & Headings (Plus Jakarta Sans):** Geometric forms with humanist touches. Its circular contours and modern terminals mirror the claymorphic radius tokens.
- **Reading & Neutral Interface (Inter):** High x-height, neutral aperture, and optimized legibility at sub-pixel levels across varying monitor DPI configurations.
- **Developer Chrome, URLs & Telemetry (JetBrains Mono):** Distinct monospaced tabular figures used strictly for URL bars, resource monitors, memory counters, security certificates, and developer tooling.

### Typographic Execution Guidelines
- Omnibar web addresses display protocol (`https://`) and parameters in 40% dimmed lavender, while the host domain uses bold JetBrains Mono at full opacity.
- Dynamic tracking: Display sizes drop down to `-0.03em` for tight visual coherence; interface labels under `12px` utilize `+0.04em` tracking with semi-bold weights to avoid blur during anti-aliasing against dark glass backdrops.

## Layout & Spacing

Desktop browser chrome demands high structural discipline; every pixel directly impacts webview canvas real estate. The spacing system relies on an exact 4px sub-grid with an 8px macro rhythm.

### Layout Philosophy
- **Modular Spatial Framing:** The browser chrome does not pin edge-to-edge as dead rectangular blocks. It utilizes a floating shell structure where toolbars, vertical tab rails, and peripheral drawers float with uniform outer margins over the base canvas.
- **Sidebar Dock Metrics:**
  - Compact Icon Rail: Fixed `56px`
  - Expanded Vertical Tab Deck: `240px` to `320px` fluid resizable
  - Utility/Dev Drawer: `380px` minimum width
- **Omnibar Command Ceiling:** Centered floating pill capped at a maximum width of `680px`, remaining vertically centered in the upper control shell with balanced `space-sm` padding.

### Responsive Breakpoints & Adaptability
- **Compact Window Mode (< 768px):** The vertical tab rail automatically collapses to an iconic rail (`56px`). Top control strip switches to single-line density where URL and action chips coalesce into unified swipeable breadcrumbs.
- **Standard Desktop (768px - 1440px):** Full dual-mode tab deck support (horizontal floating tabs or vertical collapsible stack). Web content area retains isolated fluid scale with structural inset borders.
- **Ultrawide Canvas (> 1440px):** Side inspectors and split webview instances sit on equal 12-column sub-divisions separated by `gutter-desktop`.

## Elevation & Depth

Visual hierarchy is constructed through physical surface extrusions and multi-layered atmospheric lighting, rather than flat drop shadows or structural black dividing lines.

### Depth Archetypes

1. **Recessed Wells (Tabs Basin, Omnibar Input Surface):**
   - Inner shadow: `inset 0 2px 4px rgba(0, 0, 0, 0.4), inset 0 1px 2px rgba(0, 0, 0, 0.6)`
   - Subtle outer rim: `0 1px 0 rgba(255, 255, 255, 0.05)`
   - Effect: Elements look routed into the chassis surface.

2. **Clay Surfaces (Floating Tabs, Control Buttons, Group Tiles):**
   - Dual-source balance:
     - Specular top rim: `inset 0 1px 1px rgba(255, 255, 255, 0.18)`
     - Soft bottom core: `inset 0 -2px 4px rgba(0, 0, 0, 0.25)`
     - Ambient drop occlusion: `0 4px 12px rgba(0, 0, 0, 0.35), 0 1px 2px rgba(0, 0, 0, 0.2)`
   - Effect: Elements feel soft, opaque, rounded, and physical.

3. **Floating Frosted Glass (Command HUD, Menus, Active Overlays):**
   - Translucent substrate: `background: rgba(19, 19, 37, 0.72)`
   - Optical filtration: `backdrop-filter: blur(28px) saturate(180%)`
   - Perimeter edge glow: `box-shadow: 0 0 0 1px rgba(199, 210, 254, 0.12), 0 16px 36px rgba(0, 0, 0, 0.5)`

4. **Active Radiant Glow:**
   - Elements associated with real-time operations, selected tabs, or media playback bleed their primary or secondary color into the adjacent chassis via diffused volumetric backlights:
     - Indigo focus: `0 0 20px rgba(99, 102, 241, 0.35)`
     - Fuchsia accent: `0 0 20px rgba(217, 70, 239, 0.3)`
     - Cyan transmission: `0 0 20px rgba(6, 182, 212, 0.3)`

## Shapes

The design system employs continuous smooth curves (squircle-biased geometry) to sustain its claymorphic aesthetic without appearing child-like or cartoonish.

### Curvature Guidelines
- **Micro Tokens (`rounded-sm` / 0.25rem):** Sub-elements such as code tags, scrollbar thumbs, and status indicator dots.
- **Component Base (`rounded-md` / 0.75rem):** Dropdown items, tooltips, list row selections, tab sub-groups.
- **Clay Structural Modules (`rounded-lg` / 1rem):** Standard buttons, active browser tabs, omnibar search entry, webview frame container corners.
- **Macro Panels & Modals (`rounded-xl` / 1.5rem):** Command palettes, settings surface containers, media floating picture-in-picture frames.
- **Pills (`rounded-full` / 9999px):** URL security chips, active audio/camera permission flags, workspace switcher triggers.

## Components

### 1. Browser Tabs & Group Rails
- **Resting Tab:** Integrated seamlessly into the tray with transparent backgrounds and muted lavender text. Hover triggers a subtle claymorphic surface elevation (`#1b1b36`) with a top specular line.
- **Active Tab:** Fully materialized clay surface (`#242448`). Features an inset top highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.2)`), soft bottom ambient shadow, and an indigo bottom beam or lateral accent pill (`#6366f1`).
- **Audio/Active Pips:** Micro-pills rendered in translucent rose or fuchsia resting inside the tab corner with pulsing low-frequency wave graphics.

### 2. The Omnibar (Unified Command & Location Field)
- **Resting State:** Recessed architectural cavity (`#0c0c16`) with an inset shadow, flanked by a secure context shield in cyan (`#06b6d4`). JetBrains Mono typography for web addresses.
- **Focused State:** Transforms into a floating frosted glass command canvas extending downward. The backdrop blurs the active webpage. The omnibar borders ignite with an indigo-to-fuchsia gradient edge highlight (`1px`), exposing search shortcuts, quick web queries, and instant spatial commands.

### 3. Action Buttons
- **Primary Clay Buttons:** Solid indigo fill (`#6366f1`) with dual lighting: top highlight `rgba(255, 255, 255, 0.25)` and lower rim shade `rgba(0, 0, 0, 0.3)`. Active state triggers physical compression (`transform: translateY(1px) scale(0.98)` and inset shadow inversion).
- **Secondary Ghost Clay:** Translucent charcoal basalt (`rgba(27, 27, 54, 0.6)`) with `1px` perimeter tint. Specular edge activates on mouse hover.
- **Destructive/Critical:** Tinted rose (`#e11d48`) utilizing identical extruded lighting values.

### 4. Interactive Chips & Status Badges
- Continuous pill geometry (`rounded-full`) with `space-xs` vertical and `space-sm` horizontal padding.
- Used for sandbox shields, memory trackers (e.g., `42 MB` in JetBrains Mono), and workspace partitions.
- Embedded status dots carry soft glowing blooms matching their state color (green for authenticated, cyan for TLS 1.3, yellow for proxy, rose for blocked trackers).

### 5. Checkboxes, Radio Controls & Toggles
- **Toggles:** Physical recessed oval tracks (`#0c0c16`) with extruded clay thumb knobs (`#ffffff` with `#c7d2fe` ambient occlusion). When toggled on, the track illuminates with electric violet (`#5046e5`).
- **Checkboxes:** Curved squares (`6px` radius) with recessed borders. Check state fills with vibrant indigo, sporting an inset light rim and a crisp white micro-tick.

### 6. Floating Glass Cards & Inspector Tiles
- Background composed of `#131325` at 70% opacity with `24px` backdrop blur.
- Cards do not use hard drop shadows; they float via an exterior `1px` specular stroke gradient (running from `rgba(255, 255, 255, 0.15)` at the top down to `rgba(255, 255, 255, 0.02)` at the bottom base).
- Headers sit across an integrated hairline separator with bold Plus Jakarta Sans titling.

### 7. Custom Browser Chrome Components
- **Workspace Switcher:** Vertical stack of squircle clay buttons. Active workspace exhibits an outer cyan or fuchsia underglow ring.
- **Split-View Divider:** Tactile handle bar featuring three embossed vertical micro-ribs. Dragging reveals an illuminated electric violet laser guideline through the webview partition.
- **Download & Performance Ray:** Monospaced data readout displaying disk throughput with real-time gradient sparkline indicators anchored in the status strip.