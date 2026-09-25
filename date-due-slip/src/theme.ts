export const colors = {
  paper: "#F3E6C9",
  paperDark: "#E8D5A8",
  /** Screen root — translucent so site bg photo shows through */
  screen: "rgba(243, 230, 201, 0.78)",
  ink: "#2A1F14",
  muted: "#6B5344",
  stamp: "#C23B22",
  stampOk: "#2F6B4F",
  /** FAB «+ пост» — peacock teal, not used elsewhere */
  fab: "#0D7377",
  fabPressed: "#095456",
  line: "#C9B48A",
  white: "#FFFBF3",
  danger: "#8B1E12",
};

/** UI scale (~+12.5% vs base; was 1.5, −25%) */
export const U = 1.125;
export const s = (n: number) => Math.round(n * U);
export const fs = (n: number) => Math.round(n * U);

/** Fully rounded (pill) corners for all action buttons */
export const btnRadius = 999;

export const DEFAULT_API = "http://192.168.0.213:18088";
