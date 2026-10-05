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
  TextInput,
  View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { ApiError, ExchangeApi, HandoffApi, LibraryApi, MsgApi, ShelfApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { formatMsgTime, otherPartners } from "../../src/chat";
import { CopyQrScanModal } from "../../src/CopyQrScanModal";
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
  const [libInvitesIn, setLibInvitesIn] = useState<
    {
      id: number;
      library_name: string;
      from_username: string;
      message: string;
      overlap: {
        isbn: string;
        title: string;
        combined: number;
        target_count: number;
        source_count: number;
      }[];
    }[]
  >([]);
  const [libInvitesOut, setLibInvitesOut] = useState<
    {
      id: number;
      library_name: string;
      to_username: string;
      message: string;
      status?: string;
      overlap?: {
        isbn: string;
        title: string;
        combined: number;
        target_count: number;
        source_count: number;
      }[];
    }[]
  >([]);
  const [libActionsIn, setLibActionsIn] = useState<
    {
      id: number;
      title: string;
      isbn: string;
      existing_count: number;
      count?: number;
      action_type?: string;
      action_type_label?: string;
      initiator_username: string;
      library_name: string;
    }[]
  >([]);
  const [libActionsOut, setLibActionsOut] = useState<
    {
      id: number;
      title: string;
      isbn: string;
      existing_count: number;
      count?: number;
      action_type?: string;
      action_type_label?: string;
      initiator_username: string;
      library_name: string;
    }[]
  >([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [dueDraft, setDueDraft] = useState<Record<number, string>>({});
  const [handoffScan, setHandoffScan] = useState<{
    id: number;
    action: "give" | "receive";
  } | null>(null);

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
    setLibInvitesIn(thread.library_invites_in || []);
    setLibInvitesOut(thread.library_invites_out || []);
    setLibActionsIn(thread.library_actions_in || []);
    setLibActionsOut(thread.library_actions_out || []);
    const drafts: Record<number, string> = {};
    for (const row of [...(thread.pending_in || []), ...(thread.pending_out || [])]) {
      if (row.proposed_due_date) drafts[row.id] = row.proposed_due_date;
    }
    setDueDraft((prev) => ({ ...prev, ...drafts }));
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

  const acceptLibraryInvite = async (inviteId: number) => {
    try {
      const res = await LibraryApi.acceptInvite(inviteId, {});
      await load();
      if (res.awaiting_admin_isbn) {
        Alert.alert(
          "Об'єднання",
          "Ви погодились. Адміністратор підтвердить кількість спільних ISBN."
        );
        return;
      }
      Alert.alert("Об'єднання", "Бібліотеки об'єднано. Книги з’являться у «Моя полиця».");
    } catch (e) {
      if (e instanceof ApiError && e.status === 202) {
        await load();
        Alert.alert(
          "Об'єднання",
          (e.payload as { detail?: string }).detail ||
            "Ви погодились. Адміністратор підтвердить кількість спільних ISBN."
        );
        return;
      }
      Alert.alert("Merge", e instanceof ApiError ? e.message : String(e));
    }
  };

  const acceptReq = (e: Exchange) => {
    const transmit = !!e.is_transmission;
    const swap = e.kind === "exchange" && !!e.offer_shelf;
    const due = dueDraft[e.id] || e.proposed_due_date || null;
    const dueHint = !swap && due ? `\nТермін повернення: ${due}.` : "";
    Alert.alert(
      transmit ? "Схвалити передачу?" : e.kind === "exchange" ? "Прийняти обмін?" : "Прийняти позику?",
      transmit
        ? `Схвалити передачу «${e.target_shelf.book.title}» → ${e.requester.username}? Книга лишиться у поточного позичальника, доки обидва не підтвердять фізичну передачу в чаті.${dueHint}`
        : `Підтвердити запит щодо «${e.target_shelf.book.title}»?${dueHint}`,
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: transmit ? "Схвалити" : "Прийняти",
          onPress: () =>
            runAction(() => ExchangeApi.accept(e.id, !swap ? due : null), "Обміни"),
        },
      ]
    );
  };

  const proposeDue = (e: Exchange) => {
    const due = (dueDraft[e.id] || e.proposed_due_date || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(due)) {
      Alert.alert("Термін", "Вкажіть дату у форматі РРРР-ММ-ДД.");
      return;
    }
    runAction(async () => {
      await ExchangeApi.proposeDue(e.id, due);
      Alert.alert("Термін", "Пропозицію надіслано.");
    }, "Термін");
  };

  const confirmDue = (e: Exchange) => {
    runAction(async () => {
      await ExchangeApi.confirmDue(e.id);
      Alert.alert("Термін", "Дату погоджено.");
    }, "Термін");
  };

  const dueControls = (e: Exchange) => {
    if (e.offer_shelf || e.kind === "exchange") return null;
    return (
      <View style={styles.dueBox}>
        <TextInput
          style={styles.dueInput}
          value={dueDraft[e.id] ?? e.proposed_due_date ?? ""}
          onChangeText={(t) => setDueDraft((d) => ({ ...d, [e.id]: t }))}
          placeholder="РРРР-ММ-ДД"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
          maxLength={10}
        />
        <View style={styles.actionBtns}>
          {e.can_propose_due !== false ? (
            <Pressable onPress={() => proposeDue(e)}>
              <Text style={styles.accept}>Запропонувати дату</Text>
            </Pressable>
          ) : null}
          {e.can_confirm_due ? (
            <Pressable onPress={() => confirmDue(e)}>
              <Text style={styles.accept}>Погодити термін</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
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
          Чат за активною позикою / передачею / запитом на об'єднання бібліотек.
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
                    onPress={() => setHandoffScan({ id: h.id, action: "give" })}
                  >
                    <Text style={styles.accept}>
                      {h.requires_qr_scan ? "Скан QR → віддав" : "Я віддав (скан)"}
                    </Text>
                  </Pressable>
                ) : null}
                {h.can_confirm_receive ? (
                  <Pressable
                    onPress={() => setHandoffScan({ id: h.id, action: "receive" })}
                  >
                    <Text style={styles.accept}>
                      {h.requires_qr_scan ? "Скан QR → отримав" : "Я отримав (скан)"}
                    </Text>
                  </Pressable>
                ) : null}
                {h.can_confirm_give && !h.requires_qr_scan ? (
                  <Pressable
                    onPress={() =>
                      runAction(() => HandoffApi.confirmGive(h.id), "Віддача")
                    }
                  >
                    <Text style={styles.reject}>Без QR</Text>
                  </Pressable>
                ) : null}
                {h.can_confirm_receive && !h.requires_qr_scan ? (
                  <Pressable
                    onPress={() =>
                      runAction(() => HandoffApi.confirmReceive(h.id), "Отримання")
                    }
                  >
                    <Text style={styles.reject}>Без QR</Text>
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

      {(libActionsIn.length > 0 || libActionsOut.length > 0) && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Запити до бібліотеки</Text>
          {libActionsIn.map((a) => (
            <View key={a.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={4}>
                {a.action_type_label || "Дія"} · @{a.initiator_username}
                {a.title ? `: ${a.title}` : ""}
                {a.action_type === "add_copy" && a.isbn
                  ? ` (ISBN ${a.isbn}${a.existing_count ? `, уже ${a.existing_count}` : ""})`
                  : a.count && a.count > 1
                    ? ` (${a.count} шт.)`
                    : ""}
              </Text>
              <View style={styles.actionBtns}>
                <Pressable
                  onPress={() =>
                    runAction(() => LibraryApi.resolveAction(a.id, true), "Бібліотека")
                  }
                >
                  <Text style={styles.accept}>Підтвердити</Text>
                </Pressable>
                <Pressable
                  onPress={() =>
                    runAction(() => LibraryApi.resolveAction(a.id, false), "Бібліотека")
                  }
                >
                  <Text style={styles.reject}>Відхилити</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {libActionsOut.map((a) => (
            <View key={a.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={2}>
                Очікує адміна: {a.action_type_label || "дія"}
                {a.title ? ` — ${a.title}` : ""}
              </Text>
            </View>
          ))}
        </View>
      )}

      {(libInvitesIn.length > 0 || libInvitesOut.length > 0) && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Об'єднання бібліотек</Text>
          {libInvitesIn.map((inv) => (
            <View key={inv.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={3}>
                Від @{inv.from_username} · {inv.library_name}
                {inv.message ? `\n${inv.message}` : ""}
                {inv.overlap?.length
                  ? `\nСпільних ISBN: ${inv.overlap.length} — після згоди адмін підтвердить кількість`
                  : ""}
              </Text>
              <View style={styles.actionBtns}>
                <Pressable onPress={() => acceptLibraryInvite(inv.id)}>
                  <Text style={styles.accept}>Підтвердити</Text>
                </Pressable>
                <Pressable
                  onPress={() =>
                    runAction(() => LibraryApi.rejectInvite(inv.id), "Merge")
                  }
                >
                  <Text style={styles.reject}>Відхилити</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {libInvitesOut.map((inv) => (
            <View key={inv.id} style={styles.actionRow}>
              {inv.status === "awaiting_isbn" ? (
                <>
                  <Text style={styles.actionText} numberOfLines={4}>
                    @{inv.to_username} погодився · {inv.library_name}
                    {"\n"}Підтвердіть кількість спільних ISBN у «Спільна бібліотека»
                    {inv.overlap?.length ? ` (${inv.overlap.length} ISBN).` : "."}
                  </Text>
                  <View style={styles.actionBtns}>
                    <Pressable onPress={() => router.push("/library")}>
                      <Text style={styles.accept}>Відкрити форму</Text>
                    </Pressable>
                    <Pressable
                      onPress={() =>
                        runAction(() => LibraryApi.cancelInvite(inv.id), "Merge")
                      }
                    >
                      <Text style={styles.reject}>Скасувати</Text>
                    </Pressable>
                  </View>
                </>
              ) : (
                <>
                  <Text style={styles.actionText} numberOfLines={2}>
                    Очікує @{inv.to_username} · {inv.library_name}
                  </Text>
                  <Pressable
                    onPress={() =>
                      runAction(() => LibraryApi.cancelInvite(inv.id), "Merge")
                    }
                  >
                    <Text style={styles.reject}>Скасувати</Text>
                  </Pressable>
                </>
              )}
            </View>
          ))}
        </View>
      )}

      {pendingIn.length > 0 && (
        <View style={styles.actionBox}>
          <Text style={styles.actionTitle}>Вхідні запити</Text>
          {pendingIn.map((e) => (
            <View key={e.id} style={styles.actionRow}>
              <Text style={styles.actionText} numberOfLines={3}>
                {e.is_transmission ? "Передача: " : e.kind === "exchange" ? "Обмін: " : "Позика: "}
                {e.target_shelf.book.title}
                {e.proposed_due_date && e.kind !== "exchange"
                  ? ` · до ${e.proposed_due_date}${
                      e.due_date_proposer === "owner" ? " (від вас)" : ""
                    }${e.due_date_confirmed ? " · погоджено" : ""}`
                  : ""}
              </Text>
              {dueControls(e)}
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
              <Text style={styles.actionText} numberOfLines={3}>
                {e.is_transmission ? "Очікує передачі: " : "Очікує: "}
                {e.target_shelf.book.title}
                {e.proposed_due_date && e.kind !== "exchange"
                  ? ` · до ${e.proposed_due_date}${
                      e.due_date_proposer === "owner" ? " (від власника)" : ""
                    }${e.due_date_confirmed ? " · погоджено" : ""}`
                  : ""}
              </Text>
              {dueControls(e)}
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
              {item.exchange_request_detail?.can_accept ? (
                <View style={styles.actionBtns}>
                  <Pressable
                    onPress={() => {
                      const d = item.exchange_request_detail!;
                      const due = d.proposed_due_date || null;
                      runAction(
                        () =>
                          ExchangeApi.accept(
                            d.id,
                            d.kind !== "exchange" ? due : null
                          ),
                        "Обміни"
                      );
                    }}
                  >
                    <Text style={styles.accept}>
                      {item.exchange_request_detail.is_transmission
                        ? "Схвалити"
                        : "Підтвердити"}
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      runAction(
                        () => ExchangeApi.reject(item.exchange_request_detail!.id),
                        "Обміни"
                      )
                    }
                  >
                    <Text style={styles.reject}>Відхилити</Text>
                  </Pressable>
                </View>
              ) : item.exchange_request_detail?.can_cancel ? (
                <Pressable
                  onPress={() =>
                    runAction(
                      () => ExchangeApi.cancel(item.exchange_request_detail!.id),
                      "Обміни"
                    )
                  }
                >
                  <Text style={styles.reject}>Скасувати запит</Text>
                </Pressable>
              ) : item.exchange_request != null ? (
                <Pressable onPress={() => router.push("/exchanges")}>
                  <Text style={styles.exLink}>Запити на обмін / позику</Text>
                </Pressable>
              ) : null}
              {item.exchange_request_detail?.can_confirm_due ? (
                <Pressable
                  onPress={() =>
                    runAction(
                      () => ExchangeApi.confirmDue(item.exchange_request_detail!.id),
                      "Термін"
                    )
                  }
                >
                  <Text style={styles.accept}>
                    Погодити термін
                    {item.exchange_request_detail.proposed_due_date
                      ? ` (${item.exchange_request_detail.proposed_due_date})`
                      : ""}
                  </Text>
                </Pressable>
              ) : null}
              {item.library_invite?.can_respond ? (
                <View style={styles.actionBtns}>
                  <Pressable onPress={() => acceptLibraryInvite(item.library_invite!.id)}>
                    <Text style={styles.accept}>Підтвердити</Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      runAction(
                        () => LibraryApi.rejectInvite(item.library_invite!.id),
                        "Merge"
                      )
                    }
                  >
                    <Text style={styles.reject}>Відхилити</Text>
                  </Pressable>
                </View>
              ) : null}
              {item.library_invite?.status === "awaiting_isbn" &&
              item.library_invite?.can_cancel ? (
                <View style={styles.actionBtns}>
                  <Pressable onPress={() => router.push("/library")}>
                    <Text style={styles.accept}>Підтвердити ISBN</Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      runAction(
                        () => LibraryApi.cancelInvite(item.library_invite!.id),
                        "Merge"
                      )
                    }
                  >
                    <Text style={styles.reject}>Скасувати merge</Text>
                  </Pressable>
                </View>
              ) : null}
              {item.library_action?.can_decide ? (
                <View style={styles.actionBtns}>
                  <Pressable
                    onPress={() =>
                      runAction(
                        () => LibraryApi.resolveAction(item.library_action!.id, true),
                        "Бібліотека"
                      )
                    }
                  >
                    <Text style={styles.accept}>Підтвердити</Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      runAction(
                        () => LibraryApi.resolveAction(item.library_action!.id, false),
                        "Бібліотека"
                      )
                    }
                  >
                    <Text style={styles.reject}>Відхилити</Text>
                  </Pressable>
                </View>
              ) : null}
              {item.library_invite?.can_cancel ? (
                <Pressable
                  onPress={() =>
                    runAction(
                      () => LibraryApi.cancelInvite(item.library_invite!.id),
                      "Merge"
                    )
                  }
                >
                  <Text style={styles.reject}>Скасувати запит</Text>
                </Pressable>
              ) : null}
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
        <Pressable
          onPress={send}
          disabled={busy || !body.trim()}
          accessibilityRole="button"
          accessibilityLabel="Відправити"
          style={[styles.sendBtn, (!body.trim() || busy) && { opacity: 0.4 }]}
        >
          <Ionicons name="send" size={22} color={colors.stamp} />
        </Pressable>
      </View>

      <CopyQrScanModal
        visible={!!handoffScan}
        onClose={() => setHandoffScan(null)}
        hint="Відскануйте QR примірника для підтвердження"
        onScan={(payload) => {
          const job = handoffScan;
          setHandoffScan(null);
          if (!job) return;
          runAction(
            () =>
              job.action === "give"
                ? HandoffApi.confirmGive(job.id, payload)
                : HandoffApi.confirmReceive(job.id, payload),
            job.action === "give" ? "Віддача" : "Отримання"
          );
        }}
      />
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
  actionBtns: { flexDirection: "row", flexWrap: "wrap", gap: 16, marginTop: 4 },
  dueBox: { marginBottom: 6 },
  dueInput: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: "#fff",
    color: colors.ink,
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 14,
    marginBottom: 4,
  },
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
  sendBtn: { paddingVertical: 10, paddingHorizontal: 8, justifyContent: "center" },
});
