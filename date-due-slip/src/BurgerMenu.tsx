import { type ReactNode, useState } from "react";
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

/** Shared header control chrome — matches Search / + Пост (ink fill). */
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
        <Ionicons name="menu" size={24} color={colors.white} />
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
                <Ionicons name="close" size={22} color={colors.white} />
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

/** Bell + burger for stack/tab headers — same ink chip style app-wide. */
export function HeaderActions() {
  return (
    <View style={styles.actions}>
      <NotifBell variant="ink" />
      <BurgerMenu />
    </View>
  );
}

const styles = StyleSheet.create({
  hit: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
    borderWidth: 1,
    borderColor: colors.ink,
    marginLeft: 6,
  },
  hitPressed: {
    backgroundColor: "#1a140e",
  },
  closeHit: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  dot: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: "#E53935",
    borderWidth: 1.5,
    borderColor: colors.ink,
  },
  actions: { flexDirection: "row", alignItems: "center" },
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
  itemOn: {
    backgroundColor: colors.ink,
    marginHorizontal: -8,
    paddingHorizontal: 16,
    borderBottomColor: colors.ink,
  },
  itemText: { color: colors.ink, fontSize: 16, fontWeight: "600" },
  itemTextOn: { color: colors.white, fontWeight: "800" },
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
