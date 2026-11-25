const WAVE = "M-20 892 C150 840 300 822 460 826 C700 832 850 905 1060 897 C1300 888 1500 830 1700 795";

/** Fixed, decorative lighting: soft colour pools, the large curved light at the top and the glowing wave at the bottom.
 *  variant="app" keeps only the soft pools (calmer behind data screens). */
export default function Backdrop({ variant = "home" }: { variant?: "home" | "app" }) {
  return (
    <div className={`backdrop backdrop--${variant}`} aria-hidden="true">
      <div className="backdrop__pool backdrop__pool--violet" />
      <div className="backdrop__pool backdrop__pool--blue" />
      <div className="backdrop__pool backdrop__pool--amber" />
      {variant === "home" && <svg className="backdrop__art" viewBox="0 0 1672 941" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="arcStroke" x1="330" y1="0" x2="1340" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#8a63ff" />
            <stop offset="0.5" stopColor="#7f8cff" />
            <stop offset="1" stopColor="#3f8cff" />
          </linearGradient>
          <linearGradient id="arcFadeGrad" x1="0" y1="40" x2="0" y2="520" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#fff" />
            <stop offset="0.5" stopColor="#fff" stopOpacity="0.4" />
            <stop offset="0.95" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="arcFade" maskUnits="userSpaceOnUse" x="0" y="0" width="1672" height="941">
            <rect width="1672" height="941" fill="url(#arcFadeGrad)" />
          </mask>
          <linearGradient id="waveStroke" x1="0" y1="0" x2="1672" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#6b4dff" stopOpacity="0.9" />
            <stop offset="0.28" stopColor="#b783ff" />
            <stop offset="0.5" stopColor="#e9a0b8" />
            <stop offset="0.66" stopColor="#ffa35e" />
            <stop offset="0.85" stopColor="#7c7bff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#5b8dff" stopOpacity="0.25" />
          </linearGradient>
          <linearGradient id="waveFill" x1="0" y1="0" x2="1672" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#6b4dff" stopOpacity="0.28" />
            <stop offset="0.5" stopColor="#2a1f55" stopOpacity="0.08" />
            <stop offset="0.7" stopColor="#ff9a4d" stopOpacity="0.07" />
            <stop offset="1" stopColor="#3d5bff" stopOpacity="0.1" />
          </linearGradient>
          <filter id="softGlow" x="-10%" y="-40%" width="120%" height="180%">
            <feGaussianBlur stdDeviation="9" />
          </filter>
        </defs>

        <g className="backdrop__arc" mask="url(#arcFade)">
          <circle cx="836" cy="560" r="513" stroke="url(#arcStroke)" strokeWidth="9" fill="none" opacity="0.4" filter="url(#softGlow)" />
          <circle cx="836" cy="560" r="513" stroke="url(#arcStroke)" strokeWidth="1.6" fill="none" opacity="0.85" />
        </g>

        <path d={`${WAVE} L1700 960 L-20 960 Z`} fill="url(#waveFill)" />
        <path d={WAVE} stroke="url(#waveStroke)" strokeWidth="16" fill="none" opacity="0.85" filter="url(#softGlow)" />
        <path d={WAVE} stroke="url(#waveStroke)" strokeWidth="3" fill="none" />
      </svg>}
    </div>
  );
}
