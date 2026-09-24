import { useCallback, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, ExchangeApi, HandoffApi, MsgApi, ShelfApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { formatMsgTime, otherPartners } from "../../src/chat";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { colors } from "../../src/theme";
import type { Exchange, LoanHandoff, Message, Shelf, User } from "../../src/types";

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const partnerId = Number(id);
  const { user } = useAuth();
  const router = useRouter();
  const listRef = useRef<FlatList<Message>>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [partner, setPartner] = useState<User | null>(null);
  const [partners, setPartners] = useState<User[]>([]);
  const [pendingIn, setPendingIn] = useState<Exchange[]>([]);
  const [pendingOut, setPendingOut] = useState<Exchange[]>([]);
  const [pendingReturns, setPendingReturns] = useState<Shelf[]>([]);
  const [handoffs, setHandoffs] = useState<LoanHandoff[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const [thread, plist] = await Promise.all([
      MsgApi.thread(partnerId),
      MsgApi.partners().catch(() => [] as User[]),
    ]);
    setMessages(thread.messages);
    setPartner(thread.partner);
    setPartners(plist);
    setPendingIn(thread.pending_in || []);
    setPendingOut(thread.pending_out || []);
    setPendingReturns(thread.pending_returns || []);
    setHandoffs(thread.handoffs || []);
    requestAnimationFrame(() => {
      if (thread.messages.length) {
        listRef.current?.scrollToEnd({ animated: false });
      }
    });
  };

  useFocusEffect(
    useCallback(() => {
      if (!partnerId) return;
      load().catch((e) =>
        Alert.alert("Чат", e instanceof ApiError ? e.message : String(e), [
          { text: "До обмінів", onPress: () => router.replace("/exchanges") },
          { text: "OK" },
        ])
      );
      const t = setInterval(() => {
        load().catch(() => undefined);
      }, 8000);
      return () => clearInterval(t);
    }, [partnerId])
  );

  const send = async () => {
    const text = body.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await MsgApi.send(partnerId, text);
      setBody("");
      await load();
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    } catch (e) {
      Alert.alert("Чат", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runAction = async (fn: () => Promise<unknown>, label: string) => {
    try {
      await fn();
      await load();
    } catch (e) {
      Alert.alert(label, e instanceof ApiError ? e.message : String(e));
    }
  };

  const acceptReq = (e: Exchange) => {
    const transmit = !!e.is_transmission;
    Alert.alert(
      transmit ? "Схвалити передачу?" : e.kind === "exchange" ? "Прийняти обмін?" : "Прийняти позику?",
      transmit
        ? `Схвалити передачу «${e.target_shelf.book.title}» → ${e.requester.username}? Книга лишиться у поточного позичальника, доки обидва не підтвердять фізичну передачу в чаті.`
        : `Підтвердити запит щодо «${e.target_shelf.book.title}»?`,
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: transmit ? "Схвалити" : "Прийняти",
          onPress: () => runAction(() => ExchangeApi.accept(e.id), "Обміни"),
        },
      ]
    );
  };

  const others = partner ? otherPartners(partners, partner.id) : [];
  const handoffParticipants = handoffs.flatMap((h) => h.participants || []);
  const triangle = [
    ...new Map(
      [...handoffParticipants, ...others].filter((p) => p.id !== partner?.id).map((p) => [p.id, p])
    ).values(),
  ];

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.screen }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 64 : 0}
    >
      <View style={styles.head}>
        <Text style={styles.headTitle}>{partner?.username || "…"}</Text>
        <Text style={styles.headHint}>
          Чат за активною позикою / передачею. Під час фізичної передачі власник і обидва
          позичальники в чаті; після підтвердження отримання попередній позичальник виходить.
        </Text>
        <Pressable onPress={() => router.push("/exchanges")}>
          <Text style={styles.back}>← До обмінів</Text>
        </Pressable>
      </View>

      {pendingReturns.length > 0 && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Підтвердити повернення</Text>
          {pendingReturns.map((s) => (
            <View key={s.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={2}>
                {s.book.title}
              </Text>
              <Pressable
                onPress={() =>
                  runAction(() => ShelfApi.confirmReturn(s.id), "Повернення")
                }
              >
                <Text style={styles.accept}>Підтвердити</Text>
              </Pressable>
            </View>
          ))}
        </View>
      )}

      {handoffs.length > 0 && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Фізична передача</Text>
          {handoffs.map((h) => (
            <View key={h.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={3}>
                {h.book_title}
                {"\n"}
                {h.owner.username} · {h.from_user.username} → {h.to_user.username}
                {" · "}
                {h.status === "awaiting_give" ? "очікує віддачі" : "очікує отримання"}
              </Text>
              <View style={styles.actionBtns}>
                {h.can_confirm_give ? (
                  <Pressable
                    onPress={() =>
                      runAction(() => HandoffApi.confirmGive(h.id), "Віддача")
                    }
                  >
                    <Text style={styles.accept}>Я віддав</Text>
                  </Pressable>
                ) : null}
                {h.can_confirm_receive ? (
                  <Pressable
                    onPress={() =>
                      runAction(() => HandoffApi.confirmReceive(h.id), "Отримання")
                    }
                  >
                    <Text style={styles.accept}>Я отримав</Text>
                  </Pressable>
                ) : null}
                {h.can_cancel ? (
                  <Pressable
                    onPress={() => runAction(() => HandoffApi.cancel(h.id), "Скасування")}
                  >
                    <Text style={styles.reject}>Скасувати</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          ))}
        </View>
      )}

      {pendingIn.length > 0 && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Вхідні запити</Text>
          {pendingIn.map((e) => (
            <View key={e.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={2}>
                {e.is_transmission ? "Передача: " : e.kind === "exchange" ? "Обмін: " : "Позика: "}
                {e.target_shelf.book.title}
              </Text>
              <View style={styles.actionBtns}>
                <Pressable onPress={() => acceptReq(e)}>
                  <Text style={styles.accept}>
                    {e.is_transmission ? "Схвалити" : "Прийняти"}
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => runAction(() => ExchangeApi.reject(e.id), "Обміни")}
                >
                  <Text style={styles.reject}>Відхилити</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>
      )}

      {pendingOut.length > 0 && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Ваші запити</Text>
          {pendingOut.map((e) => (
            <View key={e.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={2}>
                {e.is_transmission ? "Очікує передачі: " : "Очікує: "}
                {e.target_shelf.book.title}
              </Text>
              <Pressable onPress={() => runAction(() => ExchangeApi.cancel(e.id), "Обміни")}>
                <Text style={styles.reject}>Скасувати</Text>
              </Pressable>
            </View>
          ))}
        </View>
      )}

      {triangle.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.othersBar}
          contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}
        >
          <Text style={styles.othersLabel}>Учасники:</Text>
          {triangle.map((p) => (
            <Pressable key={p.id} onPress={() => router.replace(`/chat/${p.id}`)}>
              <Text style={styles.otherChip}>{p.username}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 12, flexGrow: 1 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              try {
                await load();
              } finally {
                setRefreshing(false);
              }
            }}
          />
        }
        ListEmptyComponent={
          <Text style={styles.empty}>Ще немає повідомлень у цьому чаті.</Text>
        }
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        renderItem={({ item }) => {
          const mine = item.sender.id === user?.id;
          const inbound = item.recipient.id === user?.id;
          return (
            <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
              <Text style={styles.meta}>
                <Text style={styles.metaStrong}>{mine ? "Ви" : item.sender.username}</Text>
                {" · "}
                {formatMsgTime(item.created_at)}
                {inbound && item.read_at ? " · прочитано" : ""}
              </Text>
              <Text style={[styles.msg, mine && styles.msgMine]}>{item.body}</Text>
              {item.exchange_request != null && (
                <Pressable onPress={() => router.push("/exchanges")}>
                  <Text style={styles.exLink}>Запити на обмін / позику</Text>
                </Pressable>
              )}
            </View>
          );
        }}
      />

      <View style={styles.bar}>
        <CyrillicTextInput
          style={styles.input}
          value={body}
          onChangeText={setBody}
          placeholder="повідомлення"
          placeholderTextColor={colors.muted}
          multiline
          editable={!busy}
        />
        <Pressable onPress={send} disabled={busy || !body.trim()}>
          <Text style={[styles.send, (!body.trim() || busy) && { opacity: 0.4 }]}>
            Надіслати
          </Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  head: {
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
  },
  headTitle: { fontWeight: "800", color: colors.ink, fontSize: 18 },
  headHint: { color: colors.muted, fontSize: 12, marginTop: 4, lineHeight: 16 },
  back: { color: colors.stamp, fontWeight: "700", marginTop: 6, fontSize: 13 },
  actionBox: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.paper,
    borderBottomWidth: 1,
    borderColor: colors.line,
  },
  actionTitle: { fontWeight: "800", color: colors.ink, fontSize: 13, marginBottom: 6 },
  actionRow: { marginBottom: 8 },
  actionText: { color: colors.ink, fontSize: 13, marginBottom: 4 },
  actionBtns: { flexDirection: "row", gap: 16 },
  accept: { color: colors.stamp, fontWeight: "800", fontSize: 14 },
  reject: { color: colors.muted, fontWeight: "700", fontSize: 14 },
  othersBar: { maxHeight: 40, borderBottomWidth: 1, borderColor: colors.line },
  othersLabel: { color: colors.muted, alignSelf: "center", marginRight: 4, fontSize: 12 },
  otherChip: {
    color: colors.ink,
    fontWeight: "700",
    paddingVertical: 8,
    paddingHorizontal: 4,
    fontSize: 13,
  },
  empty: { color: colors.muted, textAlign: "center", marginTop: 40 },
  bubble: {
    maxWidth: "88%",
    padding: 10,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.line,
  },
  mine: { alignSelf: "flex-end", backgroundColor: colors.paper },
  theirs: { alignSelf: "flex-start", backgroundColor: "#fff" },
  meta: { color: colors.muted, fontSize: 11, marginBottom: 4 },
  metaStrong: { fontWeight: "700", color: colors.ink },
  msg: { color: colors.ink, fontSize: 15, lineHeight: 20 },
  msgMine: { color: colors.ink },
  exLink: { color: colors.stamp, fontWeight: "700", marginTop: 6, fontSize: 12 },
  bar: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 10,
    borderTopWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
    gap: 8,
  },
  input: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: colors.ink,
    backgroundColor: "#fff",
  },
  send: { color: colors.stamp, fontWeight: "800", paddingVertical: 10, paddingHorizontal: 4 },
});
