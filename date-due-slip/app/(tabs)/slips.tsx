import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi, SlipApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { useAuth } from "../../src/auth";
import { colors } from "../../src/theme";
import type { Shelf } from "../../src/types";

function Slip({
  s,
  role,
  onChat,
  onConfirm,
}: {
  s: Shelf;
  role: "borrowed" | "lent";
  onChat?: () => void;
  onConfirm?: () => void;
}) {
  const overdue = s.is_overdue;
  return (
    <View style={[styles.slip, overdue && styles.overdue, s.return_pending && role === "lent" && styles.pending]}>
      <Text style={styles.library}>DATE DUE SLIP</Text>
      <BookCover uri={s.book.cover_url} size="full" bleed={0} />
      <Text style={styles.title}>{s.book.title}</Text>
      <Text style={styles.meta}>{s.book.authors || "—"}</Text>
      <View style={styles.stampBox}>
        <Text style={[styles.stamp, overdue && { color: colors.danger }]}>
          {overdue ? "OVERDUE" : s.due_date ? `DUE ${s.due_date}` : "NO DATE"}
        </Text>
        {s.days_left != null && (
          <Text style={styles.days}>
            {overdue
              ? `${Math.abs(s.days_left)} дн. прострочено`
              : `${s.days_left} дн. лишилось`}
          </Text>
        )}
      </View>
      <Text style={styles.footer}>
        {role === "borrowed"
          ? `Позичено у ${s.borrowed_from?.username}`
          : `У ${s.user.username}`}
        {s.return_pending
          ? role === "lent"
            ? " · чекає вашого підтвердження"
            : " · повернення надіслано"
          : ""}
      </Text>
      {role === "lent" && s.return_pending && onConfirm ? (
        <Pressable style={styles.confirmBtn} onPress={onConfirm}>
          <Text style={styles.confirmBtnText}>Підтвердити повернення</Text>
        </Pressable>
      ) : null}
      {onChat && (
        <Pressable onPress={onChat}>
          <Text style={styles.chat}>
            {role === "borrowed" ? "Чат з власником" : "Чат з позичальником"}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

export default function Slips() {
  const router = useRouter();
  const { user } = useAuth();
  const [borrowed, setBorrowed] = useState<Shelf[]>([]);
  const [lent, setLent] = useState<Shelf[]>([]);
  const [loanDays, setLoanDays] = useState(14);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await SlipApi.list();
    setBorrowed(data.borrowed);
    setLent(data.lent);
    setLoanDays(data.loan_days);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) =>
        Alert.alert("Slips", e instanceof ApiError ? e.message : String(e))
      );
    }, [])
  );

  const confirmReturn = async (s: Shelf) => {
    try {
      await ShelfApi.confirmReturn(s.id);
      Alert.alert("Повернення", "Підтверджено.");
      await load();
    } catch (e) {
      Alert.alert("Повернення", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ paddingBottom: 40 }}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
    >
      <Text style={styles.hint}>
        Стандартний термін позики: {loanDays} днів від прийняття запиту.
      </Text>
      <Text style={styles.sec}>Мої позики</Text>
      {borrowed.length === 0 ? (
        <Text style={styles.empty}>Немає позичених книг</Text>
      ) : (
        borrowed.map((s) => (
          <Slip
            key={s.id}
            s={s}
            role="borrowed"
            onChat={
              s.borrowed_from
                ? () => router.push(`/chat/${s.borrowed_from!.id}`)
                : undefined
            }
          />
        ))
      )}
      <Text style={styles.sec}>Видано мною</Text>
      {lent.length === 0 ? (
        <Text style={styles.empty}>Ніхто не тримає ваші книги</Text>
      ) : (
        lent.map((s) => (
          <Slip
            key={s.id}
            s={s}
            role="lent"
            onConfirm={s.return_pending ? () => confirmReturn(s) : undefined}
            onChat={
              s.user.id !== user?.id
                ? () => router.push(`/chat/${s.user.id}`)
                : undefined
            }
          />
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  hint: { color: colors.muted, marginBottom: 16, fontSize: 13, paddingHorizontal: 16, paddingTop: 12 },
  sec: {
    color: colors.ink,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: 8,
    marginTop: 8,
    paddingHorizontal: 16,
  },
  empty: { color: colors.muted, marginBottom: 16, paddingHorizontal: 16 },
  slip: {
    borderWidth: 0,
    borderBottomWidth: 2,
    borderColor: colors.ink,
    backgroundColor: colors.white,
    padding: 0,
    paddingBottom: 16,
    marginBottom: 0,
    borderStyle: "solid",
    overflow: "hidden",
  },
  overdue: { borderColor: colors.stamp, backgroundColor: "#FBE9E5" },
  pending: { borderColor: colors.stampOk, backgroundColor: "#E8F5E9" },
  library: {
    color: colors.stamp,
    fontWeight: "800",
    letterSpacing: 2,
    fontSize: 12,
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  title: { color: colors.ink, fontSize: 16, fontWeight: "700", marginTop: 8, paddingHorizontal: 16 },
  meta: { color: colors.muted, marginTop: 2, paddingHorizontal: 16 },
  stampBox: { marginTop: 12, alignItems: "flex-end", paddingHorizontal: 16 },
  days: { color: colors.muted, fontSize: 12, marginTop: 2 },
  footer: {
    color: colors.ink,
    marginTop: 12,
    fontSize: 12,
    paddingHorizontal: 16,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 8,
  },
  stamp: { color: colors.stampOk, fontWeight: "900", fontSize: 18, letterSpacing: 1 },
  confirmBtn: {
    marginTop: 12,
    marginHorizontal: 16,
    backgroundColor: colors.stampOk,
    paddingVertical: 12,
  },
  confirmBtnText: { color: "#fff", fontWeight: "800", textAlign: "center" },
  chat: { color: colors.stamp, fontWeight: "800", marginTop: 10, paddingHorizontal: 16 },
});
