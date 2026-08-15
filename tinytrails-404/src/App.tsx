import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Menu, X } from 'lucide-react';

const NAV_ITEMS = ['About Us', 'Programs', 'Reviews', 'FAQ', 'Contacts'];

const VIDEO_URL =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260713_234424_b1332b69-2e69-4302-8dbc-40f86846afbd.mp4';

function Logo() {
  return (
    <a href="/" className="flex items-center">
      <div className="grid grid-cols-2 gap-0.5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-white rounded-full" />
        ))}
      </div>
      <span className="text-white font-bold text-lg sm:text-xl ml-1">TinyTrails</span>
    </a>
  );
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scaleY, setScaleY] = useState(1);
  const textRef = useRef<HTMLDivElement>(null);

  // Stretch the background "404" so it fills the viewport height
  useEffect(() => {
    const measure = () => {
      const el = textRef.current;
      if (el && el.offsetHeight > 0) {
        setScaleY(window.innerHeight / el.offsetHeight);
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  // Lock body scroll while the menu is open
  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [menuOpen]);

  return (
    <div
      className="w-full h-screen overflow-hidden flex flex-col"
      style={{ background: 'linear-gradient(to bottom, #FF8233 0%, #FDAC55 100%)' }}
    >
      {/* Background "404" + oval, masked to fade out at the bottom */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          opacity: 0.8,
          maskImage: 'linear-gradient(to bottom, black 40%, transparent 95%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black 40%, transparent 95%)',
        }}
      >
        <div className="relative w-full h-full flex items-center justify-center">
          <div
            ref={textRef}
            className="text-white font-black leading-none tracking-tighter whitespace-nowrap"
            style={{
              fontSize: 'clamp(200px, 48vw, 800px)',
              transform: `scale(1.15, ${scaleY * 1.4})`,
            }}
          >
            404
          </div>
          <div
            className="absolute bg-white rounded-full h-[22vh] sm:h-[26vh] md:h-[50vh]"
            style={{
              width: 'clamp(120px, 20vw, 400px)',
              transform: `scaleY(${scaleY})`,
              transformOrigin: 'center',
            }}
          />
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative z-20 flex items-center justify-between px-4 sm:px-6 md:px-12 py-4 sm:py-5">
        <Logo />
        <div className="hidden md:flex gap-1">
          {NAV_ITEMS.map((item) => (
            <a
              key={item}
              href="#"
              className="px-4 py-1.5 text-sm font-medium rounded-full bg-white text-[#F16524] hover:opacity-90 transition-colors"
            >
              {item}
            </a>
          ))}
        </div>
        <button
          onClick={() => setMenuOpen(true)}
          className="flex items-center gap-2 px-4 py-2 sm:px-5 sm:py-2.5 rounded-full text-white bg-[#F16524] hover:opacity-90 transition-colors"
        >
          <Menu className="w-4 h-4" />
          <span className="text-sm font-medium hidden sm:inline">Menu</span>
        </button>
      </nav>

      {/* Menu overlay */}
      <div
        className={`fixed inset-0 z-50 transition-[visibility] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          menuOpen ? 'visible' : 'invisible'
        }`}
        aria-hidden={!menuOpen}
      >
        <div
          className={`absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-500 ${
            menuOpen ? 'opacity-100' : 'opacity-0'
          }`}
          onClick={() => setMenuOpen(false)}
        />
        <div
          className={`absolute top-0 right-0 h-full w-full sm:w-[380px] transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            menuOpen ? 'translate-x-0' : 'translate-x-full'
          }`}
          style={{ background: 'linear-gradient(135deg, #FF6B1A 0%, #FF9642 100%)' }}
        >
          <div className="flex items-center justify-between px-6 py-5">
            <Logo />
            <button
              onClick={() => setMenuOpen(false)}
              className="w-10 h-10 rounded-full bg-white/20 text-white hover:bg-white/30 flex items-center justify-center transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex flex-col gap-2 px-6 pt-4">
            {NAV_ITEMS.map((item, i) => (
              <a
                key={item}
                href="#"
                className={`px-6 py-4 text-lg font-semibold text-white rounded-2xl bg-white/10 hover:bg-white/20 transition-all duration-300 ${
                  menuOpen ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                }`}
                style={{ transitionDelay: menuOpen ? `${150 + i * 60}ms` : '0ms' }}
              >
                {item}
              </a>
            ))}
          </div>
          <div className="absolute bottom-0 left-0 right-0 p-6">
            <a
              href="/"
              className={`w-full inline-flex items-center justify-center gap-2 py-4 rounded-full bg-white font-semibold text-base text-[#F16524] hover:scale-[1.02] transition-all duration-300 ${
                menuOpen ? 'opacity-100' : 'opacity-0'
              }`}
              style={{ transitionDelay: menuOpen ? '450ms' : '0ms' }}
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </a>
          </div>
        </div>
      </div>

      {/* Center video */}
      <div
        className="absolute inset-0 flex items-center justify-center pointer-events-none"
        style={{ marginTop: 'calc(-6vh - 40px)' }}
      >
        <div className="w-[120vw] h-[85vh] sm:w-[70vw] sm:h-[70vh] md:w-[62vw] md:h-[78vh]">
          <video
            autoPlay
            loop
            muted
            playsInline
            className="w-full h-full object-contain pointer-events-none mix-blend-darken"
          >
            <source src={VIDEO_URL} type="video/mp4" />
          </video>
        </div>
      </div>

      {/* Bottom content */}
      <div className="relative z-30 mt-auto pb-8 sm:pb-16 flex flex-col items-center text-center px-4">
        <h1 className="text-white text-lg sm:text-xl md:text-2xl font-medium mb-3 sm:mb-4">
          Oops, something went wrong!
        </h1>
        <a
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-4 rounded-full text-white font-semibold text-sm sm:text-base bg-[#F16524] hover:scale-105 hover:shadow-lg transition-all"
        >
          <ArrowLeft className="w-4 h-4 sm:w-5 sm:h-5" />
          Back to Home
        </a>
      </div>
    </div>
  );
}
