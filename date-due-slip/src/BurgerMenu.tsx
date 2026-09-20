import { useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { usePathname, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NotifBell } from "./NotifBell";
import { colors } from "./theme";
import { useUnread } from "./unread";

type Link = {
  label: string;
  href: string;
  badge?: boolean;
};

const LINKS: Link[] = [
  { label: "Стрічка", href: "/(tabs)" },
  { label: "Моя полиця", href: "/(tabs)/shelf" },
  { label: "Реченець", href: "/(tabs)/slips" },
  { label: "Чужі полиці", href: "/(tabs)/browse" },
  { label: "Ще", href: "/(tabs)/more", badge: true },
  { label: "Сповіщення", href: "/notifications", badge: true },
  { label: "Обміни / чати", href: "/exchanges" },
];

function pathMatch(pathname: string, href: string) {
  if (href === "/(tabs)" || href === "/(tabs)/") {
    return (
      pathname === "/" ||
      pathname.endsWith("/(tabs)") ||
      pathname.endsWith("/(tabs)/") ||
      pathname === "/index"
    );
  }
  const key = href.replace("/(tabs)/", "/").replace("/(tabs)", "");
  return pathname.includes(key) || pathname.includes(href);
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
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={8}
        style={styles.hit}
        accessibilityRole="button"
        accessibilityLabel="Меню"
      >
        <Ionicons name="menu" size={26} color={colors.ink} />
        {unread > 0 ? <View style={styles.dot} /> : null}
      </Pressable>

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
              <Pressable onPress={() => setOpen(false)} hitSlop={8}>
                <Ionicons name="close" size={24} color={colors.ink} />
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

/** Bell + burger for stack/tab headers. */
export function HeaderActions() {
  return (
    <View style={styles.actions}>
      <NotifBell />
      <BurgerMenu />
    </View>
  );
}

const styles = StyleSheet.create({
  hit: {
    minWidth: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 4,
  },
  dot: {
    position: "absolute",
    top: 8,
    right: 6,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#E53935",
  },
  actions: { flexDirection: "row", alignItems: "center", gap: 2 },
  backdrop: { flex: 1, flexDirection: "row", justifyContent: "flex-end" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.35)" },
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
  itemOn: { backgroundColor: colors.white, marginHorizontal: -8, paddingHorizontal: 8 },
  itemText: { color: colors.ink, fontSize: 16, fontWeight: "600" },
  itemTextOn: { color: colors.stamp, fontWeight: "800" },
  badge: {
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#E53935",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "800" },
});
