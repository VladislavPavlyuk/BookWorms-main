import { useMemo, useRef, useState } from "react";
import {
  LayoutChangeEvent,
  PanResponder,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { colors, fs, s } from "./theme";

const AGE_MIN = 0;
const AGE_MAX = 18;
const TICKS = [0, 3, 5, 7, 10, 12, 15, 18] as const;

function clampAge(n: number) {
  return Math.max(AGE_MIN, Math.min(AGE_MAX, Math.round(n)));
}

function labelAge(n: number) {
  return n >= AGE_MAX ? "18+" : String(n);
}

type Props = {
  minAge: number;
  maxAge: number;
  onChange: (minAge: number, maxAge: number) => void;
  compact?: boolean;
};

/** Dual-thumb 0–18+ age range — same scale as My Library web. */
export function AgeRangeDual({ minAge, maxAge, onChange, compact }: Props) {
  const [trackW, setTrackW] = useState(0);
  const lo = Math.min(minAge, maxAge);
  const hi = Math.max(minAge, maxAge);
  const active = useRef<"min" | "max" | null>(null);
  const stateRef = useRef({ lo, hi, trackW, onChange });
  stateRef.current = { lo, hi, trackW, onChange };

  const trackPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (evt) => {
          const { trackW: w, lo: a, hi: b, onChange: cb } = stateRef.current;
          const age = clampAge((evt.nativeEvent.locationX / Math.max(1, w)) * AGE_MAX);
          active.current =
            Math.abs(age - a) <= Math.abs(age - b) ? "min" : "max";
          if (active.current === "min") cb(Math.min(age, b), b);
          else cb(a, Math.max(age, a));
        },
        onPanResponderMove: (evt) => {
          const { trackW: w, lo: a, hi: b, onChange: cb } = stateRef.current;
          const age = clampAge((evt.nativeEvent.locationX / Math.max(1, w)) * AGE_MAX);
          if (active.current === "min") cb(Math.min(age, b), b);
          else if (active.current === "max") cb(a, Math.max(age, a));
        },
        onPanResponderRelease: () => {
          active.current = null;
        },
      }),
    []
  );

  const loPct = (lo / AGE_MAX) * 100;
  const hiPct = (hi / AGE_MAX) * 100;
  const thumb = compact ? s(14) : s(18);
  const trackH = compact ? s(8) : s(10);

  return (
    <View style={[styles.wrap, compact && styles.wrapCompact]}>
      <Text style={[styles.label, compact && styles.labelCompact]}>
        Вік: {labelAge(lo)}–{labelAge(hi)}
      </Text>
      {!compact ? (
        <View style={styles.ticks}>
          {TICKS.map((t) => (
            <Text key={t} style={styles.tick}>
              {labelAge(t)}
            </Text>
          ))}
        </View>
      ) : (
        <View style={styles.ticks}>
          <Text style={styles.tick}>0</Text>
          <Text style={styles.tick}>18+</Text>
        </View>
      )}
      <View
        style={[styles.trackHit, compact && styles.trackHitCompact]}
        onLayout={(e: LayoutChangeEvent) => setTrackW(e.nativeEvent.layout.width)}
        {...trackPan.panHandlers}
      >
        <View style={[styles.trackBg, { height: trackH, borderRadius: trackH / 2 }]} />
        <View
          style={[
            styles.trackFill,
            {
              left: `${loPct}%`,
              width: `${Math.max(0, hiPct - loPct)}%`,
              height: trackH,
              borderRadius: trackH / 2,
            },
          ]}
        />
        <View
          style={[
            styles.thumb,
            {
              left: `${loPct}%`,
              width: thumb,
              height: thumb,
              marginLeft: -thumb / 2,
              borderRadius: thumb / 2,
            },
          ]}
        />
        <View
          style={[
            styles.thumb,
            {
              left: `${hiPct}%`,
              width: thumb,
              height: thumb,
              marginLeft: -thumb / 2,
              borderRadius: thumb / 2,
            },
          ]}
        />
      </View>
    </View>
  );
}

export function ageFilterParams(minAge: number, maxAge: number): {
  age_min: string;
  age_max: string;
} {
  const a = clampAge(Math.min(minAge, maxAge));
  const b = clampAge(Math.max(minAge, maxAge));
  if (a === AGE_MIN && b === AGE_MAX) return { age_min: "", age_max: "" };
  return { age_min: String(a), age_max: String(b) };
}

export function parseAgeParam(raw: string | undefined, fallback: number) {
  if (raw == null || raw === "") return fallback;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? clampAge(n) : fallback;
}

const styles = StyleSheet.create({
  wrap: { marginBottom: s(10) },
  wrapCompact: { marginBottom: 0 },
  label: {
    color: colors.ink,
    fontWeight: "700",
    fontSize: fs(13),
    marginBottom: s(6),
  },
  labelCompact: {
    fontSize: fs(12),
    marginBottom: s(2),
    color: colors.muted,
    fontWeight: "600",
  },
  ticks: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: s(4),
  },
  tick: { color: colors.muted, fontSize: fs(11), fontWeight: "600" },
  trackHit: {
    height: s(28),
    justifyContent: "center",
    marginBottom: s(4),
  },
  trackHitCompact: {
    height: s(24),
    marginBottom: 0,
  },
  trackBg: {
    position: "absolute",
    left: 0,
    right: 0,
    height: s(10),
    borderRadius: 5,
    backgroundColor: colors.line,
  },
  trackFill: {
    position: "absolute",
    height: s(10),
    borderRadius: 5,
    backgroundColor: "#198754",
  },
  thumb: {
    position: "absolute",
    width: s(18),
    height: s(18),
    marginLeft: -s(9),
    borderRadius: 9,
    backgroundColor: "#198754",
    borderWidth: 2,
    borderColor: colors.white,
  },
});
