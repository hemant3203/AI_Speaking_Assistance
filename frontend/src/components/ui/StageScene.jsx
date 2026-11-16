/**
 * The product's signature image: a lamp, a beam, a pool of light on the boards.
 * It is decorative everywhere it appears, so it stays hidden from assistive tech.
 */
import { useId } from 'react';

/** Soft cone and floor pool. Sits behind content with absolute positioning. */
export function SpotBeam({ className = '', intensity = 1 }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '');
  return (
    <svg viewBox="0 0 400 300" preserveAspectRatio="none" aria-hidden="true" className={`pointer-events-none absolute ${className}`}>
      <defs>
        <linearGradient id={`beam${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFC971" stopOpacity={0.42 * intensity} />
          <stop offset="0.75" stopColor="#FFB84D" stopOpacity={0.12 * intensity} />
          <stop offset="1" stopColor="#FFB84D" stopOpacity={0.04 * intensity} />
        </linearGradient>
        <radialGradient id={`pool${id}`}>
          <stop offset="0" stopColor="#FFC971" stopOpacity={0.5 * intensity} />
          <stop offset="0.6" stopColor="#FFB84D" stopOpacity={0.16 * intensity} />
          <stop offset="1" stopColor="#FFB84D" stopOpacity="0" />
        </radialGradient>
        <filter id={`soft${id}`} x="-20%" y="-5%" width="140%" height="110%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      <polygon points="178,-10 222,-10 340,272 60,272" fill={`url(#beam${id})`} filter={`url(#soft${id})`} />
      <ellipse cx="200" cy="272" rx="178" ry="26" fill={`url(#pool${id})`} />
    </svg>
  );
}

/** The full scene for the auth pages: curtains, boards, a mic waiting in the light. */
export function StageScene({ className = '' }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '');
  const boards = [-420, -270, -130, 0, 130, 270, 420];
  return (
    <svg viewBox="0 0 800 1000" preserveAspectRatio="xMidYMax slice" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id={`wall${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0B0908" />
          <stop offset="1" stopColor="#1A1410" />
        </linearGradient>
        <linearGradient id={`floor${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#241B14" />
          <stop offset="1" stopColor="#0E0B09" />
        </linearGradient>
        <linearGradient id={`beam${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFD48A" stopOpacity="0.6" />
          <stop offset="0.7" stopColor="#FFB84D" stopOpacity="0.17" />
          <stop offset="1" stopColor="#FFB84D" stopOpacity="0.07" />
        </linearGradient>
        <radialGradient id={`pool${id}`}>
          <stop offset="0" stopColor="#FFD48A" stopOpacity="0.85" />
          <stop offset="0.55" stopColor="#FFB84D" stopOpacity="0.32" />
          <stop offset="1" stopColor="#FFB84D" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`fold${id}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#2B100C" />
          <stop offset="0.5" stopColor="#47190F" />
          <stop offset="1" stopColor="#1C0B08" />
        </linearGradient>
        <linearGradient id={`curtainFade${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0B0908" stopOpacity="0.15" />
          <stop offset="1" stopColor="#0B0908" stopOpacity="0.7" />
        </linearGradient>
        <filter id={`soft${id}`} x="-20%" y="-5%" width="140%" height="110%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>

      <rect width="800" height="760" fill={`url(#wall${id})`} />

      {[0, 62, 124, 186].map((x) => (
        <g key={`left${x}`}>
          <rect x={x - 40} y="-10" width="66" height="780" fill={`url(#fold${id})`} />
          <rect x={800 - x - 26} y="-10" width="66" height="780" fill={`url(#fold${id})`} />
        </g>
      ))}
      <rect x="-40" y="-10" width="880" height="780" fill={`url(#curtainFade${id})`} />

      <rect y="760" width="800" height="240" fill={`url(#floor${id})`} />
      {boards.map((offset) => (
        <line key={offset} x1={400 + offset * 0.5} y1="760" x2={400 + offset * 2.2} y2="1000" stroke="#000" strokeOpacity="0.4" strokeWidth="1.5" />
      ))}
      <line x1="0" y1="760" x2="800" y2="760" stroke="#000" strokeOpacity="0.5" strokeWidth="2" />

      {/* Off-centre on purpose: the pitch text sits on the left, clear of the microphone. */}
      <g transform="translate(170 0)">
      <polygon points="370,20 430,20 640,818 160,818" fill={`url(#beam${id})`} filter={`url(#soft${id})`} />
      <ellipse cx="400" cy="822" rx="300" ry="62" fill={`url(#pool${id})`} />

      {/* Lamp */}
      <rect x="396" y="-4" width="8" height="18" fill="#0A0807" />
      <rect x="368" y="10" width="64" height="20" rx="6" fill="#0A0807" />
      <rect x="376" y="28" width="48" height="4" rx="2" fill="#FFD48A" />

      {/* Microphone on a stand, in silhouette against the light */}
      <ellipse cx="400" cy="826" rx="46" ry="9" fill="#0B0807" opacity="0.8" />
      <rect x="396.5" y="608" width="7" height="216" rx="3" fill="#120D0A" />
      <rect x="360" y="812" width="80" height="11" rx="5.5" fill="#120D0A" />
      <g transform="rotate(-16 400 600)">
        <rect x="388" y="540" width="24" height="52" rx="12" fill="#17110D" />
        <rect x="392" y="590" width="16" height="30" rx="5" fill="#120D0A" />
        <path d="M391 553h18M391 562h18M391 571h18" stroke="#FFD48A" strokeOpacity="0.5" strokeWidth="1.5" />
        <rect x="388" y="540" width="3" height="50" rx="1.5" fill="#FFD48A" opacity="0.55" />
      </g>

      {/* Dust drifting through the beam */}
      <g fill="#FFE5B4">
        <circle className="animate-drift" cx="345" cy="340" r="2" />
        <circle className="animate-drift" style={{ animationDelay: '1.4s' }} cx="430" cy="240" r="1.6" />
        <circle className="animate-drift" style={{ animationDelay: '2.6s' }} cx="460" cy="470" r="2.2" />
        <circle className="animate-drift" style={{ animationDelay: '3.8s' }} cx="330" cy="520" r="1.6" />
        <circle className="animate-drift" style={{ animationDelay: '5s' }} cx="395" cy="420" r="1.4" />
      </g>
      </g>
    </svg>
  );
}
