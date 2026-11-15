import type { SVGProps } from "react";

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

type P = SVGProps<SVGSVGElement>;

export const RainIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 15a4 4 0 0 1-.6-7.95A5.5 5.5 0 0 1 17 8a3.5 3.5 0 0 1 .5 7H7Z" />
    <path d="m9 18-1 2.5M13 18l-1 2.5M17 18l-1 2.5" />
  </svg>
);

export const DropIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 3.5s-6 6.4-6 10.5a6 6 0 0 0 12 0c0-4.1-6-10.5-6-10.5Z" />
  </svg>
);

export const WavesIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M3 8c2 0 2-1.5 4.5-1.5S9.5 8 12 8s2-1.5 4.5-1.5S18.5 8 21 8" />
    <path d="M3 13c2 0 2-1.5 4.5-1.5S9.5 13 12 13s2-1.5 4.5-1.5S18.5 13 21 13" />
    <path d="M3 18c2 0 2-1.5 4.5-1.5S9.5 18 12 18s2-1.5 4.5-1.5S18.5 18 21 18" />
  </svg>
);

export const QuestionIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.6 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.5M12 16.8v.2" />
  </svg>
);

export const ThermoIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M10 13.5V5a2 2 0 1 1 4 0v8.5a4 4 0 1 1-4 0Z" />
    <path d="M12 9v7" />
  </svg>
);

export const ArrowUp = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </svg>
);

export const ArrowDown = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </svg>
);

export const CloseIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const PlusIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const GripIcon = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    {[7, 12, 17].map((y) => (
      <g key={y}>
        <circle cx="9" cy={y} r="1.4" />
        <circle cx="15" cy={y} r="1.4" />
      </g>
    ))}
  </svg>
);

export const PlayIcon = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M8 5.5v13l10.5-6.5L8 5.5Z" />
  </svg>
);

export const PauseIcon = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <rect x="6.5" y="5.5" width="4" height="13" rx="1" />
    <rect x="13.5" y="5.5" width="4" height="13" rx="1" />
  </svg>
);

export const WATER_ICONS: Record<string, (p: P) => React.JSX.Element> = {
  rain_only: RainIcon,
  some_irrigation: DropIcon,
  fully_irrigated: WavesIcon,
  not_sure: QuestionIcon,
};

/** Moist-soil colours for the soil tiles. */
export const SOIL_SWATCH: Record<string, string | undefined> = {
  sandy: "#e4cb86",
  loamy: "#8a6038",
  silty: "#bcae97",
  clay: "#a4532f",
};
