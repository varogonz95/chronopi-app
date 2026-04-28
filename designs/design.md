# Design System: Status Sanctuary

## Visual Language
A minimalist, high-impact design language optimized for small-form-factor digital signage. The system prioritizes immediate glanceability through bold color-coding, massive iconography, and a rigid layout hierarchy.

## Design Tokens

### Colors
The system uses functional color-coding to represent availability states.
*   **Available (Green):** `#0F5238` (Primary), `#E8F5E9` (Surface Container)
*   **Busy (Red):** `#8B1A1A` (Primary), `#FFEBEE` (Surface Container)
*   **Focusing (Purple):** `#4A3B5D` (Primary), `#F3E5F5` (Surface Container)
*   **OOO (Blue-Gray):** `#546E7A` (Primary), `#ECEFF1` (Surface Container)
*   **Neutral:** White `#FFFFFF`, Subtle Divider `#E0E0E0`

### Typography
*   **Status Label:** Massive, Bold Sans-Serif (e.g., 'Manrope' or 'Inter'). Focus on readability from 5+ feet.
*   **Descriptions:** Uppercase, tracking-heavy secondary text for role/state clarification.
*   **Event Details:** Medium weight for titles, light weight for metadata (time, labels).

### Layout & Spacing
*   **Structure:** 3/4 (Top) to 1/4 (Bottom) vertical split.
*   **Container:** Single card with large corner radius (e.g., `32px`).
*   **Separation:** A single, subtle horizontal rule separates the hero banner from the upcoming event section.

### Iconography
*   **Hero Icons:** Central, large-scale, and bold weight.
*   **Available:** Checkmark
*   **Busy:** Minus/Dash
*   **Focusing:** Moon
*   **OOO:** Airplane

## Component Guidelines

### Hero Banner
The hero banner occupies the top 75% of the screen. It must contain the state icon, the state title in large font, and a short, uppercase description. The background color must reflect the current state.

### Upcoming Event Section
The bottom 25% section displays the "Up Next" label, the event title, a time range (e.g., 03:30 PM — 04:30 PM), and a relative time badge (e.g., "in 45m"). This section should use a lighter, neutral background to contrast with the hero banner.
