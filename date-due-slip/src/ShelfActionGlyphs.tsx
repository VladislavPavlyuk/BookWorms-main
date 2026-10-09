import type { ReactElement } from "react";
import { StyleSheet, View } from "react-native";

export type ShelfActionIcon =
  | "add"
  | "check"
  | "qr"
  | "return"
  | "library"
  | "barcode"
  | "history"
  | "chat"
  | "tags"
  | "edit"
  | "people"
  | "cloud"
  | "cash"
  | "list"
  | "trash"
  | "close";

type GlyphProps = { color?: string; size?: number };

/** Classic + (create post). */
function AddGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2.5, size * 0.14);
  const len = size * 0.72;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          position: "absolute",
          width: len,
          height: t,
          borderRadius: t,
          backgroundColor: color,
        }}
      />
      <View
        style={{
          position: "absolute",
          width: t,
          height: len,
          borderRadius: t,
          backgroundColor: color,
        }}
      />
    </View>
  );
}

/** Classic ✓ */
function CheckGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2.5, size * 0.12);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.48,
          height: size * 0.28,
          borderLeftWidth: t,
          borderBottomWidth: t,
          borderColor: color,
          transform: [{ rotate: "-45deg" }, { translateY: -size * 0.06 }],
        }}
      />
    </View>
  );
}

/** Classic QR frame. */
function QrGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  const box = size * 0.78;
  const corner = size * 0.28;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View style={{ width: box, height: box, position: "relative" }}>
        {/* TL */}
        <View
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: corner,
            height: corner,
            borderTopWidth: t,
            borderLeftWidth: t,
            borderColor: color,
          }}
        />
        {/* TR */}
        <View
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            width: corner,
            height: corner,
            borderTopWidth: t,
            borderRightWidth: t,
            borderColor: color,
          }}
        />
        {/* BL */}
        <View
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            width: corner,
            height: corner,
            borderBottomWidth: t,
            borderLeftWidth: t,
            borderColor: color,
          }}
        />
        {/* BR */}
        <View
          style={{
            position: "absolute",
            bottom: 0,
            right: 0,
            width: corner,
            height: corner,
            borderBottomWidth: t,
            borderRightWidth: t,
            borderColor: color,
          }}
        />
        <View
          style={{
            position: "absolute",
            top: box * 0.36,
            left: box * 0.36,
            width: box * 0.28,
            height: box * 0.28,
            backgroundColor: color,
          }}
        />
      </View>
    </View>
  );
}

/** Classic ↩ return arrow. */
function ReturnGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2.5, size * 0.12);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.55,
          height: size * 0.42,
          borderLeftWidth: t,
          borderBottomWidth: t,
          borderColor: color,
          borderBottomLeftRadius: 4,
          marginLeft: size * 0.12,
        }}
      />
      <View
        style={{
          position: "absolute",
          left: size * 0.12,
          bottom: size * 0.28,
          width: 0,
          height: 0,
          borderTopWidth: size * 0.16,
          borderBottomWidth: size * 0.16,
          borderRightWidth: size * 0.22,
          borderTopColor: "transparent",
          borderBottomColor: "transparent",
          borderRightColor: color,
        }}
      />
    </View>
  );
}

/** Two book spines. */
function LibraryGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  return (
    <View
      style={{
        width: size,
        height: size,
        flexDirection: "row",
        alignItems: "flex-end",
        justifyContent: "center",
        gap: size * 0.1,
      }}
    >
      <View
        style={{
          width: size * 0.28,
          height: size * 0.72,
          borderRadius: 2,
          backgroundColor: color,
          transform: [{ rotate: "-8deg" }],
        }}
      />
      <View
        style={{
          width: size * 0.28,
          height: size * 0.78,
          borderRadius: 2,
          backgroundColor: color,
        }}
      />
    </View>
  );
}

/** Classic barcode bars. */
function BarcodeGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const bars = [0.08, 0.14, 0.08, 0.2, 0.08, 0.12, 0.08, 0.16, 0.1];
  return (
    <View
      style={{
        width: size,
        height: size,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: size * 0.04,
      }}
    >
      {bars.map((w, i) => (
        <View
          key={i}
          style={{
            width: Math.max(1.5, size * w),
            height: size * 0.7,
            backgroundColor: color,
            borderRadius: 1,
          }}
        />
      ))}
    </View>
  );
}

/** Classic clock. */
function HistoryGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  const r = size * 0.38;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: r * 2,
          height: r * 2,
          borderRadius: r,
          borderWidth: t,
          borderColor: color,
          alignItems: "center",
          justifyContent: "flex-start",
          paddingTop: r * 0.22,
        }}
      >
        <View style={{ width: t, height: r * 0.55, backgroundColor: color, borderRadius: t }} />
        <View
          style={{
            position: "absolute",
            top: r * 0.85,
            left: r * 0.95,
            width: r * 0.42,
            height: t,
            backgroundColor: color,
            borderRadius: t,
            transformOrigin: "left center",
          }}
        />
      </View>
    </View>
  );
}

/** Classic chat bubble. */
function ChatGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.72,
          height: size * 0.52,
          borderRadius: size * 0.16,
          backgroundColor: color,
        }}
      />
      <View
        style={{
          width: 0,
          height: 0,
          marginTop: -1,
          marginLeft: -size * 0.18,
          borderLeftWidth: size * 0.12,
          borderRightWidth: size * 0.12,
          borderTopWidth: size * 0.16,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
        }}
      />
    </View>
  );
}

/** Classic price tags. */
function TagsGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.55,
          height: size * 0.38,
          borderWidth: t,
          borderColor: color,
          borderRadius: 3,
          transform: [{ rotate: "-18deg" }, { translateX: -2 }],
          opacity: 0.85,
        }}
      />
      <View
        style={{
          position: "absolute",
          width: size * 0.55,
          height: size * 0.38,
          borderWidth: t,
          borderColor: color,
          borderRadius: 3,
          backgroundColor: color,
          transform: [{ rotate: "12deg" }, { translateX: 3 }],
        }}
      />
    </View>
  );
}

/** Classic pencil. */
function EditGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2.5, size * 0.14);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: t,
          height: size * 0.62,
          backgroundColor: color,
          borderRadius: t,
          transform: [{ rotate: "40deg" }],
        }}
      />
      <View
        style={{
          position: "absolute",
          bottom: size * 0.14,
          left: size * 0.18,
          width: 0,
          height: 0,
          borderLeftWidth: size * 0.12,
          borderRightWidth: size * 0.12,
          borderTopWidth: size * 0.16,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
          transform: [{ rotate: "40deg" }],
        }}
      />
    </View>
  );
}

/** Two classic person dots. */
function PeopleGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const head = size * 0.22;
  return (
    <View
      style={{
        width: size,
        height: size,
        flexDirection: "row",
        alignItems: "flex-end",
        justifyContent: "center",
        gap: size * 0.08,
      }}
    >
      {[0, 1].map((i) => (
        <View key={i} style={{ alignItems: "center" }}>
          <View
            style={{
              width: head,
              height: head,
              borderRadius: head / 2,
              backgroundColor: color,
              marginBottom: 2,
            }}
          />
          <View
            style={{
              width: size * 0.32,
              height: size * 0.28,
              borderTopLeftRadius: size * 0.16,
              borderTopRightRadius: size * 0.16,
              backgroundColor: color,
            }}
          />
        </View>
      ))}
    </View>
  );
}

/** Classic cloud + down arrow. */
function CloudGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.7,
          height: size * 0.36,
          borderRadius: size * 0.18,
          backgroundColor: color,
        }}
      />
      <View
        style={{
          position: "absolute",
          top: size * 0.22,
          left: size * 0.18,
          width: size * 0.28,
          height: size * 0.28,
          borderRadius: size * 0.14,
          backgroundColor: color,
        }}
      />
      <View
        style={{
          position: "absolute",
          top: size * 0.18,
          right: size * 0.2,
          width: size * 0.34,
          height: size * 0.34,
          borderRadius: size * 0.17,
          backgroundColor: color,
        }}
      />
      <View
        style={{
          marginTop: 2,
          width: 0,
          height: 0,
          borderLeftWidth: size * 0.14,
          borderRightWidth: size * 0.14,
          borderTopWidth: size * 0.16,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
        }}
      />
    </View>
  );
}

/** Classic banknote / cash. */
function CashGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.78,
          height: size * 0.5,
          borderRadius: 3,
          borderWidth: t,
          borderColor: color,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <View
          style={{
            width: size * 0.22,
            height: size * 0.22,
            borderRadius: size * 0.11,
            borderWidth: t,
            borderColor: color,
          }}
        />
      </View>
    </View>
  );
}

/** Classic list lines. */
function ListGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  return (
    <View
      style={{
        width: size,
        height: size,
        justifyContent: "center",
        gap: size * 0.12,
        paddingHorizontal: size * 0.08,
      }}
    >
      {[0, 1, 2].map((i) => (
        <View key={i} style={{ flexDirection: "row", alignItems: "center", gap: size * 0.1 }}>
          <View
            style={{
              width: size * 0.14,
              height: size * 0.14,
              borderRadius: 1,
              backgroundColor: color,
            }}
          />
          <View
            style={{
              flex: 1,
              height: t,
              borderRadius: t,
              backgroundColor: color,
            }}
          />
        </View>
      ))}
    </View>
  );
}

/** Classic ✕ close / cancel. */
function CloseGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2.5, size * 0.12);
  const len = size * 0.62;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          position: "absolute",
          width: len,
          height: t,
          borderRadius: t,
          backgroundColor: color,
          transform: [{ rotate: "45deg" }],
        }}
      />
      <View
        style={{
          position: "absolute",
          width: len,
          height: t,
          borderRadius: t,
          backgroundColor: color,
          transform: [{ rotate: "-45deg" }],
        }}
      />
    </View>
  );
}

/** Classic trash can. */
function TrashGlyph({ color = "#fff", size = 24 }: GlyphProps) {
  const t = Math.max(2, size * 0.1);
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: size * 0.42,
          height: t,
          backgroundColor: color,
          borderRadius: t,
          marginBottom: 2,
        }}
      />
      <View
        style={{
          width: size * 0.28,
          height: t * 0.9,
          backgroundColor: color,
          borderRadius: t,
          marginBottom: 2,
        }}
      />
      <View
        style={{
          width: size * 0.55,
          height: size * 0.48,
          borderWidth: t,
          borderColor: color,
          borderBottomLeftRadius: 3,
          borderBottomRightRadius: 3,
          borderTopWidth: 0,
        }}
      />
    </View>
  );
}

const GLYPHS: Record<ShelfActionIcon, (p: GlyphProps) => ReactElement> = {
  add: AddGlyph,
  check: CheckGlyph,
  qr: QrGlyph,
  return: ReturnGlyph,
  library: LibraryGlyph,
  barcode: BarcodeGlyph,
  history: HistoryGlyph,
  chat: ChatGlyph,
  tags: TagsGlyph,
  edit: EditGlyph,
  people: PeopleGlyph,
  cloud: CloudGlyph,
  cash: CashGlyph,
  list: ListGlyph,
  trash: TrashGlyph,
  close: CloseGlyph,
};

/** View-drawn classic glyphs — no icon font (Ionicons blanks on some builds). */
export function ShelfActionGlyph({
  name,
  color = "#fff",
  size = 24,
}: {
  name: ShelfActionIcon;
  color?: string;
  size?: number;
}) {
  const G = GLYPHS[name];
  return (
    <View style={styles.wrap} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <G color={color} size={size} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexShrink: 0 },
});
