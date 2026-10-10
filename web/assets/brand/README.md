# SpRocket CRM brand assets

## Provenance — please read
Every SVG and PNG in this package is a **new vector approximation**, recreated from the selected “Modern Negative Space” description in the referenced SpRocket logo feedback conversation. The retrieved conversation did not expose the original generated logo or latest brand-board image. No original generated artwork is included; no pixel-perfect match, sampled original color, or original font identification is claimed. The brand board in this package is a new overview of these recreated assets. PNGs are exports of the SVGs, not original AI artwork.

Design: blue sprocket, sharp diagonal rocket cut out toward the upper right, orange exhaust, SpRocket wordmark with a blue capital R, and smaller spaced CRM.

## Files and naming
- `logos/`: horizontal and stacked lockups, SVG and PNG. `light` = dark lettering for light backgrounds; `dark` = white lettering for dark backgrounds. Both have transparent backgrounds. `on-white` and `on-navy` include solid backgrounds. `mono-navy` and `mono-white` are single-color transparent assets.
- `icons/`: transparent symbols and padded 512 px app icons on light/dark tiles. Also 192 px and 180 px app exports.
- `favicons/`: SVG, 16/32/48 px PNGs, and multi-size ICO.
- `guidelines/`: palette, CSS variables, typography and usage guidance.
- `brand-board.png`: recreated brand overview.

## Implementation
Use horizontal SVG for navigation and stacked SVG for sign-in screens. Prefer SVG for responsive displays. PNG logos are exported at twice the SVG dimensions. Set a CSS width and let the height remain automatic.

```html
<img src="/brand/logos/sprocket-horizontal-light.svg" alt="SpRocket CRM" width="225">
<link rel="icon" href="/brand/favicons/favicon.ico" sizes="any">
<link rel="icon" href="/brand/favicons/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/brand/icons/apple-touch-icon.png">
```

For dark navigation use `sprocket-horizontal-dark.svg`. Color variants retain a white rocket silhouette on both light and dark backgrounds. Monochrome variants use a real transparent cutout, which takes on the background color.

SVG wordmarks use live Arial/Helvetica text, not outlined glyphs. Their appearance may vary slightly if those fonts are unavailable. Keep the included PNGs for an exact rendering of this recreation. Convert text to paths in a vector editor before supplying a font-independent print master. Do not upload the brand board as a logo.

Upload this ZIP to your CRM project chat and ask it to install the assets under a public brand directory, apply the CSS palette, and use the appropriate light/dark logo.
