import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme, type ThemePref } from "../lib/theme";

const OPTIONS: { value: ThemePref; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "system", label: "System", icon: Monitor },
  { value: "dark", label: "Dark", icon: Moon },
];

export function ThemeSwitch() {
  const { pref, setPref } = useTheme();
  return (
    <div className="segmented segmented--icons" role="radiogroup" aria-label="Theme">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={pref === value}
          className={pref === value ? "is-on" : ""}
          onClick={() => setPref(value)}
          title={label}
        >
          <Icon size={14} />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
