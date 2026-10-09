import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type LayoutChangeEvent,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, ExchangeApi, MsgApi } from "../src/api";
import { useAuth } from "../src/auth";
import { exchangeChatPartnerId } from "../src/chat";
import { ShelfLogoChip } from "../src/ShelfLogoChip";
import { colors, fs, s } from "../src/theme";
import { UserNameLink } from "../src/UserNameLink";
import type { Exchange, Shelf, User } from "../src/types";

function conditionText(e: Exchange, asOwner: boolean): string {
  const due =
    e.proposed_due_date && !e.offer_shelf
      ? ` Термін до ${e.proposed_due_date}` +
        (e.due_date_proposer === "owner" ? " (від власника)" : " (від позичальника)") +
        (e.due_date_confirmed ? ", погоджено." : ".")
      : "";
  if (e.kind === "exchange" && e.offer_shelf) {
    return asOwner
      ? `Обмін: пропонує «${e.offer_shelf.book.title}» замість вашої книги (повна передача).`
      : `Обмін: ви пропонуєте «${e.offer_shelf.book.title}» (повна передача).`;
  }
  if (e.offer_open && !e.offer_shelf) {
    return (
      (asOwner
        ? "Обмін: запитувач пропонує обрати книгу з його полиці (або прийняти як позику)."
        : "Обмін: власник може обрати книгу з вашої полиці (або прийняти як позику).") + due
    );
  }
  if (e.is_transmission) {
    return (
      (asOwner
        ? "Передача третій особі: примірник зараз у позиці. Після згоди його знімуть з поточного позичальника і видадуть цьому запитувачу."
        : "Передача: примірник зараз у когось у позиці. Власник може схвалити передачу вам (або ви в черзі до повернення).") + due
    );
  }
  return (
    (asOwner
      ? "Позика: без книги взамін. Після згоди позичальник триматиме книгу й зможе лише повернути її вам."
      : "Позика: без вашої книги взамін. Після згоди книга з’явиться у вас на полиці з терміном повернення.") +
    due
  );
}

export default function Exchanges() {
  const router = useRouter();
  const { user } = useAuth();
  const params = useLocalSearchParams<{ id?: string }>();
  const focusId = Number(params.id) || null;

  const [inn, setIn] = useState<Exchange[]>([]);
  const [out, setOut] = useState<Exchange[]>([]);
  const [hist, setHist] = useState<Exchange[]>([]);
  const [partners, setPartners] = useState<User[]>([]);
  const scrollRef = useRef<ScrollView>(null);
  const yById = useRef<Record<number, number>>({});

  const [dueDraft, setDueDraft] = useState<Record<number, string>>({});
  const [pickFor, setPickFor] = useState<number | null>(null);
  const [offerable, setOfferable] = useState<Shelf[]>([]);
  const [pickBusy, setPickBusy] = useState(false);

  const load = async () => {
    const [e, p] = await Promise.all([ExchangeApi.list(), MsgApi.partners()]);
    setIn(e.pending_in);
    setOut(e.pending_out);
    setHist(e.history);
    setPartners(p);
    const drafts: Record<number, string> = {};
    for (const row of [...e.pending_in, ...e.pending_out]) {
      if (row.proposed_due_date) drafts[row.id] = row.proposed_due_date;
    }
    setDueDraft((prev) => ({ ...prev, ...drafts }));
  };

  useFocusEffect(
    useCallback(() => {
      load()
        .then(() => {
          if (!focusId) return;
          setTimeout(() => {
            const y = yById.current[focusId];
            if (typeof y === "number") {
              scrollRef.current?.scrollTo({ y: Math.max(0, y - 12), animated: true });
            }
          }, 120);
        })
        .catch((err) =>
          Alert.alert("Обміни", err instanceof ApiError ? err.message : String(err))
        );
    }, [focusId])
  );

  const focused = useMemo(() => {
    if (!focusId) return null;
    return (
      inn.find((e) => e.id === focusId) ||
      out.find((e) => e.id === focusId) ||
      hist.find((e) => e.id === focusId) ||
      null
    );
  }, [focusId, inn, out, hist]);

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await load();
    } catch (e) {
      Alert.alert("Обміни", e instanceof ApiError ? e.message : String(e));
    }
  };

  const openChat = (e: Exchange) => {
    const pid = exchangeChatPartnerId(e, user?.id);
    if (!pid) {
      Alert.alert("Чат", "Немає спільного запиту з цим користувачем.");
      return;
    }
    router.push(`/chat/${pid}`);
  };

  const confirmAccept = (e: Exchange) => {
    const swap = !!e.offer_shelf;
    const transmit = !!e.is_transmission;
    const due = dueDraft[e.id] || e.proposed_due_date || null;
    const dueHint = !swap && due ? `\nТермін повернення: ${due}.` : "";
    Alert.alert(
      transmit
        ? "Схвалити передачу?"
        : swap
          ? "Прийняти обмін?"
          : e.offer_open
            ? "Прийняти як позику?"
            : "Прийняти позику?",
      transmit
        ? `Схвалити передачу «${e.target_shelf.book.title}» → ${e.requester.username}? Книга лишиться у поточного позичальника, доки обидва не підтвердять фізичну передачу в чаті.${dueHint}`
        : swap
          ? `Книга «${e.target_shelf.book.title}» перейде до ${e.requester.username}, а «${e.offer_shelf!.book.title}» — до вас.`
          : `Книгу «${e.target_shelf.book.title}» буде видано в позику користувачу ${e.requester.username}.${dueHint}`,
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: transmit ? "Схвалити" : "Прийняти",
          style: "default",
          onPress: () => run(() => ExchangeApi.accept(e.id, !swap ? due : null)),
        },
      ]
    );
  };

  const openPickOffer = async (e: Exchange) => {
    setPickBusy(true);
    try {
      const shelves = await ExchangeApi.offerable(e.id);
      if (!shelves.length) {
        Alert.alert("Обмін", "У запитувача зараз немає вільних книг для обміну.");
        return;
      }
      setOfferable(shelves);
      setPickFor(e.id);
    } catch (err) {
      Alert.alert("Обмін", err instanceof ApiError ? err.message : String(err));
    } finally {
      setPickBusy(false);
    }
  };

  const pickOffer = (shelfId: number) => {
    if (pickFor == null) return;
    const id = pickFor;
    setPickFor(null);
    run(async () => {
      await ExchangeApi.pickOffer(id, shelfId);
      Alert.alert("Обмін", "Книгу обрано. Можете прийняти обмін.");
    });
  };

  const proposeDue = (e: Exchange) => {
    const due = (dueDraft[e.id] || e.proposed_due_date || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(due)) {
      Alert.alert("Термін", "Вкажіть дату у форматі РРРР-ММ-ДД.");
      return;
    }
    run(async () => {
      await ExchangeApi.proposeDue(e.id, due);
      Alert.alert("Термін", "Пропозицію надіслано іншій стороні.");
    });
  };

  const confirmDue = (e: Exchange) => {
    run(async () => {
      await ExchangeApi.confirmDue(e.id);
      Alert.alert("Термін", "Дату погоджено.");
    });
  };

  const dueControls = (e: Exchange) => {
    if (e.offer_shelf || e.kind === "exchange") return null;
    return (
      <View style={styles.dueBox}>
        <Text style={styles.dueLabel}>Термін повернення</Text>
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
        <View style={styles.dueBtns}>
          {e.can_propose_due !== false ? (
            <ShelfLogoChip
              title="Запропонувати дату"
              icon="edit"
              style={styles.chip}
              onPress={() => proposeDue(e)}
            />
          ) : null}
          {e.can_confirm_due ? (
            <ShelfLogoChip
              title="Погодити термін"
              icon="check"
              style={styles.chip}
              onPress={() => confirmDue(e)}
            />
          ) : null}
        </View>
      </View>
    );
  };

  const confirmReject = (e: Exchange) => {
    Alert.alert("Відхилити запит?", `Запит щодо «${e.target_shelf.book.title}» буде відхилено.`, [
      { text: "Ні", style: "cancel" },
      {
        text: "Відхилити",
        style: "destructive",
        onPress: () => run(() => ExchangeApi.reject(e.id)),
      },
    ]);
  };

  const onCardLayout = (id: number, ev: LayoutChangeEvent) => {
    yById.current[id] = ev.nativeEvent.layout.y;
  };

  const Card = ({
    e,
    role,
    actions,
  }: {
    e: Exchange;
    role: "in" | "out" | "hist";
    actions?: ReactNode;
  }) => {
    const asOwner = role === "in" || e.shelf_owner.id === user?.id;
    const isFocus = focusId === e.id;
    return (
      <View
        style={[styles.card, isFocus && styles.cardFocus]}
        onLayout={(ev) => onCardLayout(e.id, ev)}
      >
        {isFocus ? <Text style={styles.focusTag}>з сповіщення</Text> : null}
        <Text style={styles.kind}>
          {e.is_transmission
            ? "ПЕРЕДАЧА"
            : e.offer_shelf || e.kind === "exchange"
              ? "ОБМІН"
              : e.offer_open
                ? "ПОЗИКА / ОБМІН"
                : "ПОЗИКА"}{" "}
          · {e.status}
        </Text>
        <Text style={styles.title}>{e.target_shelf.book.title}</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", marginTop: 4 }}>
          <UserNameLink user={e.requester} style={styles.meta} />
          <Text style={styles.meta}> → </Text>
          <UserNameLink user={e.shelf_owner} style={styles.meta} />
        </View>
        <Text style={styles.cond}>{conditionText(e, asOwner)}</Text>
        {role !== "hist" ? dueControls(e) : null}
        <View style={styles.row}>
          <ShelfLogoChip
            title="Чат"
            icon="chat"
            style={styles.chip}
            onPress={() => openChat(e)}
          />
          {actions}
        </View>
      </View>
    );
  };

  return (
    <ScrollView
      ref={scrollRef}
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
    >
      <Text style={styles.lead}>
        Як на десктопі: перегляньте умови (позика чи обмін), за потреби напишіть у чат, потім
        прийміть або відхиліть.
      </Text>

      {focusId && !focused ? (
        <Text style={styles.warn}>
          Запит #{focusId} не в активних списках (уже оброблений або скасований). Дивіться історію
          нижче.
        </Text>
      ) : null}

      <Text style={styles.h}>Вхідні (очікують вашої відповіді)</Text>
      {inn.length === 0 ? (
        <Text style={styles.empty}>Немає вхідних запитів.</Text>
      ) : (
        inn.map((e) => (
          <Card
            key={e.id}
            e={e}
            role="in"
            actions={
              <>
                {e.can_pick_offer ? (
                  <ShelfLogoChip
                    title={pickBusy ? "…" : "Обрати з його полиці"}
                    icon="library"
                    style={styles.chip}
                    disabled={pickBusy}
                    onPress={() => openPickOffer(e)}
                  />
                ) : null}
                <ShelfLogoChip
                  title={e.offer_open && !e.offer_shelf ? "Як позику" : "Прийняти"}
                  icon="check"
                  style={styles.chip}
                  onPress={() => confirmAccept(e)}
                />
                <ShelfLogoChip
                  title="Відхилити"
                  icon="close"
                  danger
                  style={styles.chip}
                  onPress={() => confirmReject(e)}
                />
              </>
            }
          />
        ))
      )}

      <Text style={styles.h}>Відправлені вами (очікують)</Text>
      {out.length === 0 ? (
        <Text style={styles.empty}>Немає активних відправлених запитів.</Text>
      ) : (
        out.map((e) => (
          <Card
            key={e.id}
            e={e}
            role="out"
            actions={
              <ShelfLogoChip
                title="Скасувати"
                icon="close"
                danger
                style={styles.chip}
                onPress={() =>
                  Alert.alert("Скасувати запит?", undefined, [
                    { text: "Ні", style: "cancel" },
                    {
                      text: "Скасувати",
                      style: "destructive",
                      onPress: () => run(() => ExchangeApi.cancel(e.id)),
                    },
                  ])
                }
              />
            }
          />
        ))
      )}

      <Text style={styles.h}>Чати</Text>
      {partners.length === 0 ? (
        <Text style={styles.empty}>
          Чат доступний після спільного запиту на позику або обмін.
        </Text>
      ) : (
        partners.map((p) => (
          <Pressable
            key={p.id}
            style={styles.card}
            onPress={() => router.push(`/chat/${p.id}`)}
          >
            <UserNameLink user={p} style={styles.title} />
            <Text style={styles.meta}>{p.biography || "відкрити переписку"}</Text>
          </Pressable>
        ))
      )}

      <Text style={styles.h}>Історія</Text>
      {hist.length === 0 ? (
        <Text style={styles.empty}>Поки порожньо.</Text>
      ) : (
        hist.map((e) => <Card key={e.id} e={e} role="hist" />)
      )}

      <Modal
        visible={pickFor != null}
        transparent
        animationType="slide"
        onRequestClose={() => setPickFor(null)}
      >
        <View style={styles.pickBackdrop}>
          <View style={styles.pickSheet}>
            <Text style={styles.h}>Книга з полиці запитувача</Text>
            <ScrollView style={{ maxHeight: 320 }}>
              {offerable.map((s) => (
                <Pressable
                  key={s.id}
                  style={styles.pickOpt}
                  onPress={() => pickOffer(s.id)}
                >
                  <Text style={styles.title}>{s.book.title}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <ShelfLogoChip
              title="Скасувати"
              icon="close"
              style={{ marginTop: 12 }}
              onPress={() => setPickFor(null)}
            />
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  lead: { color: colors.muted, marginBottom: s(12), lineHeight: fs(18), fontSize: fs(13) },
  warn: {
    color: colors.stamp,
    backgroundColor: "#FBE9E5",
    borderColor: colors.stamp,
    borderWidth: 1,
    padding: s(10),
    marginBottom: s(12),
    lineHeight: fs(18),
    fontSize: fs(14),
  },
  h: {
    fontWeight: "800",
    color: colors.ink,
    marginTop: s(14),
    marginBottom: 8,
    letterSpacing: 0.5,
    fontSize: fs(16),
  },
  empty: { color: colors.muted, marginBottom: 8, lineHeight: fs(18), fontSize: fs(14) },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: s(12),
    marginBottom: s(10),
  },
  cardFocus: {
    borderColor: colors.stamp,
    borderWidth: 2,
    backgroundColor: "#FFF8F0",
  },
  focusTag: {
    alignSelf: "flex-start",
    backgroundColor: colors.stamp,
    color: "#fff",
    fontSize: fs(10),
    fontWeight: "800",
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginBottom: 6,
    overflow: "hidden",
  },
  kind: { color: colors.stamp, fontSize: fs(11), fontWeight: "800" },
  title: { color: colors.ink, fontWeight: "700", marginTop: 4, fontSize: fs(16) },
  meta: { color: colors.muted, marginTop: 4, fontSize: fs(13) },
  cond: { color: colors.ink, marginTop: 8, lineHeight: fs(18), fontSize: fs(13) },
  dueBox: {
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  dueLabel: { color: colors.ink, fontWeight: "700", fontSize: fs(12), marginBottom: 4 },
  dueInput: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
    color: colors.ink,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: fs(14),
  },
  dueBtns: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: s(10),
    marginTop: s(12),
    alignItems: "center",
  },
  chip: { flexGrow: 1, flexBasis: "40%" },
  pickBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.35)",
    justifyContent: "flex-end",
  },
  pickSheet: {
    backgroundColor: colors.paper,
    padding: s(16),
    maxHeight: "70%",
  },
  pickOpt: {
    borderWidth: 1,
    borderColor: colors.line,
    padding: s(12),
    marginBottom: 8,
    backgroundColor: colors.white,
  },
});
