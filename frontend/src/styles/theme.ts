/**
 * Mainz 05 Design Theme
 * Based on official mainz05.de design system
 */

export const theme = {
  colors: {
    // Mainz 05 Brand Colors
    mainzRed: '#C8191E',
    mainzRedDark: '#A01418',
    mainzRedLight: '#E53E3E',
    mainzWhite: '#FFFFFF',
    
    // Neutral Colors
    grayLight: '#F5F5F5',
    gray: '#6B7280',
    grayDark: '#374151',
    grayNavigation: '#E5E5E5',
    
    // Status Colors
    success: '#10B981',
    error: '#EF4444',
    warning: '#F59E0B',
    info: '#3B82F6',
    
    // Overlays
    overlayDark: 'rgba(0, 0, 0, 0.4)',
    overlayLight: 'rgba(255, 255, 255, 0.9)',
  },
  
  typography: {
    fontFamily: {
      sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      mono: ['Monaco', 'Courier New', 'monospace'],
    },
    fontSize: {
      xs: '0.75rem',    // 12px
      sm: '0.875rem',   // 14px
      base: '0.9375rem', // 15px
      lg: '1rem',       // 16px
      xl: '1.125rem',   // 18px
      '2xl': '1.25rem', // 20px
      '3xl': '1.5rem',  // 24px
      '4xl': '2rem',    // 32px
      '5xl': '2.5rem',  // 40px
    },
    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800,
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75,
    },
  },
  
  spacing: {
    0: '0',
    1: '0.25rem',  // 4px
    2: '0.5rem',   // 8px
    3: '0.75rem',  // 12px
    4: '1rem',     // 16px
    5: '1.25rem',  // 20px
    6: '1.5rem',   // 24px
    8: '2rem',     // 32px
    10: '2.5rem',  // 40px
    12: '3rem',    // 48px
    16: '4rem',    // 64px
    20: '5rem',    // 80px
  },
  
  borderRadius: {
    none: '0',
    sm: '0.375rem',   // 6px
    md: '0.5rem',     // 8px
    lg: '0.75rem',    // 12px
    xl: '1rem',       // 16px
    '2xl': '1.25rem', // 20px
    full: '9999px',
  },
  
  shadows: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px rgba(0, 0, 0, 0.1)',
    inner: 'inset 0 2px 4px rgba(0, 0, 0, 0.06)',
  },
  
  transitions: {
    default: 'all 0.2s ease-in-out',
    fast: 'all 0.15s ease-in-out',
    slow: 'all 0.3s ease-in-out',
  },
  
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },
  
  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
  },
} as const;

export type Theme = typeof theme;



