import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base: IconProps = { viewBox: "0 0 32 32", fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

/** Analytics: three rising outlined bars. */
export const ChartIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <rect x="4.5" y="18" width="5.5" height="9" rx="2.75" />
    <rect x="13.25" y="11" width="5.5" height="16" rx="2.75" />
    <rect x="22" y="4" width="5.5" height="23" rx="2.75" />
  </svg>
);

/** Workflow: stacked layers. */
export const LayersIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M16 3.5 28 10l-12 6.5L4 10 16 3.5Z" />
    <path d="m4 16 12 6.5L28 16" />
    <path d="m4 22 12 6.5L28 22" />
  </svg>
);

/** Questions: speech bubble with three dots. */
export const ChatIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M7 5h18a3.5 3.5 0 0 1 3.5 3.5v10A3.5 3.5 0 0 1 25 22h-9l-6.5 5v-5H7a3.5 3.5 0 0 1-3.5-3.5v-10A3.5 3.5 0 0 1 7 5Z" />
    <circle cx="11" cy="13.5" r="0.9" fill="currentColor" />
    <circle cx="16" cy="13.5" r="0.9" fill="currentColor" />
    <circle cx="21" cy="13.5" r="0.9" fill="currentColor" />
  </svg>
);

export const ArrowIcon = (p: IconProps) => (
  <svg {...base} strokeWidth={2.4} {...p}>
    <path d="M6 16h20M18 8l8 8-8 8" />
  </svg>
);
