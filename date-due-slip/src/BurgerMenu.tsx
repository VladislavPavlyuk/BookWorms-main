import { type ReactNode, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { usePathname, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { BurgerGlyph, CloseGlyph } from "./HeaderGlyphs";
import { NotifBell } from "./NotifBell";
import { colors } from "./theme";
import { useUnread } from "./unread";

type Link = {
  label: string;
  href: string;
  badge?: boolean;
};

const LINKS: Link[] = [
  { label: "Профіль", href: "/(tabs)/more" },
  { label: "Моя полиця", href: "/(tabs)/shelf" },
  { label: "Реченець", href: "/(tabs)/slips" },
  { label: "Чужі полиці", href: "/(tabs)/browse" },
  { label: "Обміни", href: "/exchanges" },
  { label: "Сповіщення", href: "/notifications", badge: true },
];

function pathMatch(pathname: string, href: string) {
  if (href.includes("/more")) {
    return pathname.includes("/more");
  }
  const key = href.replace("/(tabs)/", "/").replace("/(tabs)", "");
  return pathname.includes(key) || pathname.includes(href);
}

/** Shared header control — paper/line/ink (same as «Фільтр»). */
export function HeaderIconButton({
  onPress,
  accessibilityLabel,
  children,
  badge,
}: {
  onPress: () => void;
  accessibilityLabel: string;
  children: ReactNode;
  badge?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={4}
      style={({ pressed }) => [styles.hit, pressed && styles.hitPressed]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
    >
      {children}
      {badge ? <View style={styles.dot} /> : null}
    </Pressable>
  );
}

/** Hamburger → slide-over with former tab links. */
export function BurgerMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { unread } = useUnread();

  const go = (href: string) => {
    setOpen(false);
    router.push(href as never);
  };

  return (
    <>
      <HeaderIconButton
        onPress={() => setOpen(true)}
        accessibilityLabel="Меню"
        badge={unread > 0}
      >
        <BurgerGlyph color={colors.ink} size={20} />
      </HeaderIconButton>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <View style={styles.backdrop}>
          <Pressable style={styles.scrim} onPress={() => setOpen(false)} />
          <View
            style={[
              styles.panel,
              { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 16 },
            ]}
          >
            <View style={styles.panelHead}>
              <Text style={styles.panelTitle}>Меню</Text>
              <Pressable onPress={() => setOpen(false)} hitSlop={8} style={styles.closeHit}>
                <CloseGlyph color={colors.ink} size={18} />
              </Pressable>
            </View>
            {LINKS.map((link) => {
              const active = pathMatch(pathname, link.href);
              const showBadge = link.badge && unread > 0;
              return (
                <Pressable
                  key={link.href}
                  style={[styles.item, active && styles.itemOn]}
                  onPress={() => go(link.href)}
                >
                  <Text style={[styles.itemText, active && styles.itemTextOn]}>{link.label}</Text>
                  {showBadge ? (
                    <View style={styles.badge}>
                      <Text style={styles.badgeText}>{unread > 99 ? "99+" : unread}</Text>
                    </View>
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </View>
      </Modal>
    </>
  );
}

/** Bell + burger for stack/tab headers — theme paper chrome app-wide. */
export function HeaderActions() {
  return (
    <View style={styles.actions}>
      <NotifBell variant="paper" />
      <BurgerMenu />
    </View>
  );
}

const styles = StyleSheet.create({
  hit: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    marginLeft: 4,
  },
  hitPressed: {
    backgroundColor: colors.paperDark,
  },
  closeHit: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
  },
  dot: {
    position: "absolute",
    top: 3,
    right: 3,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.stamp,
    borderWidth: 1.5,
    borderColor: colors.white,
  },
  actions: { flexDirection: "row", alignItems: "center", flexShrink: 0 },
  backdrop: { flex: 1, flexDirection: "row", justifyContent: "flex-end" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(42, 31, 20, 0.35)" },
  panel: {
    width: "78%",
    maxWidth: 320,
    backgroundColor: colors.paper,
    borderLeftWidth: 1,
    borderLeftColor: colors.line,
    paddingHorizontal: 16,
    zIndex: 2,
  },
  panelHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  panelTitle: { fontSize: 18, fontWeight: "800", color: colors.ink },
  item: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  itemOn: {
    backgroundColor: colors.paperDark,
    marginHorizontal: -8,
    paddingHorizontal: 16,
    borderBottomColor: colors.line,
  },
  itemText: { color: colors.ink, fontSize: 16, fontWeight: "600" },
  itemTextOn: { color: colors.ink, fontWeight: "800" },
  badge: {
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.stamp,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  badgeText: { color: colors.white, fontSize: 11, fontWeight: "800" },
});
