from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FE_DIR = ROOT_DIR.parent / "SIHFrontend" / "src" / "components" / "dashboard"

glass_style = """  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };"""

# 1. FleetStatusCounters.tsx
f1 = f"""import React from 'react';

export const FleetStatusCounters: React.FC = () => {{
{glass_style}

  return (
    <div className="grid grid-cols-2 gap-2.5 select-none shrink-0 h-[64px]">
      <div className="transition-all hover:border-white/20 h-full" style={{glassStyle}} />
      <div className="transition-all hover:border-white/20 h-full" style={{glassStyle}} />
    </div>
  );
}};

export default FleetStatusCounters;
"""
(FE_DIR / "FleetStatusCounters.tsx").write_text(f1, encoding="utf-8")
print("[OK] FleetStatusCounters.tsx cleared")

# 2. OperationalEfficiency.tsx
f2 = f"""import React from 'react';

export const OperationalEfficiency: React.FC = () => {{
{glass_style}

  return (
    <div className="rounded-2xl shrink-0 select-none overflow-hidden transition-all h-[155px]" style={{glassStyle}} />
  );
}};

export default OperationalEfficiency;
"""
(FE_DIR / "OperationalEfficiency.tsx").write_text(f2, encoding="utf-8")
print("[OK] OperationalEfficiency.tsx cleared")

# 3. DroneUnitCard.tsx (2x2 empty glass sub-panels)
f3 = f"""import React from 'react';

export const DroneUnitCard: React.FC = () => {{
{glass_style}

  return (
    <div className="grid grid-cols-2 gap-2.5 h-full min-h-[310px] select-none">
      <div className="overflow-hidden transition-all hover:border-white/20 h-full" style={{glassStyle}} />
      <div className="overflow-hidden transition-all hover:border-white/20 h-full" style={{glassStyle}} />
      <div className="overflow-hidden transition-all hover:border-white/20 h-full" style={{glassStyle}} />
      <div className="overflow-hidden transition-all hover:border-white/20 h-full" style={{glassStyle}} />
    </div>
  );
}};

export default DroneUnitCard;
"""
(FE_DIR / "DroneUnitCard.tsx").write_text(f3, encoding="utf-8")
print("[OK] DroneUnitCard.tsx cleared")

# 4. ScheduleOffset.tsx
f4 = f"""import React from 'react';

export const ScheduleOffset: React.FC = () => {{
{glass_style}

  return (
    <div className="select-none h-full overflow-hidden transition-all" style={{glassStyle}} />
  );
}};

export default ScheduleOffset;
"""
(FE_DIR / "ScheduleOffset.tsx").write_text(f4, encoding="utf-8")
print("[OK] ScheduleOffset.tsx cleared")

# 5. TimelinePanel.tsx (Bottom Right Box)
f5 = f"""import React from 'react';

export const TimelinePanel: React.FC = () => {{
{glass_style}

  return (
    <div className="select-none h-full overflow-hidden transition-all" style={{glassStyle}} />
  );
}};

export default TimelinePanel;
"""
(FE_DIR / "TimelinePanel.tsx").write_text(f5, encoding="utf-8")
print("[OK] TimelinePanel.tsx cleared")
print("All panels cleared successfully!")
