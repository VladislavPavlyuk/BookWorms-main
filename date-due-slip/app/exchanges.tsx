import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, ExchangeApi, MsgApi } from "../src/api";
import { useAuth } from "../src/auth";
import { exchangeChatPartnerId } from "../src/chat";
import { colors } from "../src/theme";
import type { Exchange, User } from "../src/types";

function conditionText(e: Exchange, asOwner: boolean): string {
  if (e.kind === "exchange" && e.offer_shelf) {
    return asOwner
      ? `Обмін: пропонує «${e.offer_shelf.book.title}» замість вашої книги (повна передача).`
      : `Обмін: ви пропонуєте «${e.offer_shelf.book.title}» (повна передача).`;
  }
  return asOwner
    ? "Позика: без книги взамін. Після згоди позичальник триматиме книгу й зможе лише повернути її вам."
    : "Позика: без вашої книги взамін. Після згоди книга з’явиться у вас на полиці з терміном повернення.";
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

  const load = async () => {
    const [e, p] = await Promise.all([ExchangeApi.list(), MsgApi.partners()]);
    setIn(e.pending_in);
    setOut(e.pending_out);
    setHist(e.history);
    setPartners(p);
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
    const swap = e.kind === "exchange" && !!e.offer_shelf;
    Alert.alert(
      swap ? "Прийняти обмін?" : "Прийняти позику?",
      swap
        ? `Книга «${e.target_shelf.book.title}» перейде до ${e.requester.username}, а «${e.offer_shelf!.book.title}» — до вас.`
        : `Книгу «${e.target_shelf.book.title}» буде видано в позику користувачу ${e.requester.username}.`,
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: "Прийняти",
          style: "default",
          onPress: () => run(() => ExchangeApi.accept(e.id)),
        },
      ]
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
          {e.kind === "borrow" ? "ПОЗИКА" : "ОБМІН"} · {e.status}
        </Text>
        <Text style={styles.title}>{e.target_shelf.book.title}</Text>
        <Text style={styles.meta}>
          {e.requester.username} → {e.shelf_owner.username}
        </Text>
        <Text style={styles.cond}>{conditionText(e, asOwner)}</Text>
        <View style={styles.row}>
          <Pressable style={styles.btnGhost} onPress={() => openChat(e)}>
            <Text style={styles.chat}>Чат</Text>
          </Pressable>
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
                <Pressable style={styles.btnOk} onPress={() => confirmAccept(e)}>
                  <Text style={styles.ok}>Прийняти</Text>
                </Pressable>
                <Pressable style={styles.btnGhost} onPress={() => confirmReject(e)}>
                  <Text style={styles.no}>Відхилити</Text>
                </Pressable>
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
              <Pressable
                style={styles.btnGhost}
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
              >
                <Text style={styles.no}>Скасувати</Text>
              </Pressable>
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
            <Text style={styles.title}>{p.username}</Text>
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  lead: { color: colors.muted, marginBottom: 12, lineHeight: 18, fontSize: 13 },
  warn: {
    color: colors.stamp,
    backgroundColor: "#FBE9E5",
    borderColor: colors.stamp,
    borderWidth: 1,
    padding: 10,
    marginBottom: 12,
    lineHeight: 18,
  },
  h: {
    fontWeight: "800",
    color: colors.ink,
    marginTop: 14,
    marginBottom: 8,
    letterSpacing: 0.5,
  },
  empty: { color: colors.muted, marginBottom: 8, lineHeight: 18 },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 12,
    marginBottom: 10,
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
    fontSize: 10,
    fontWeight: "800",
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginBottom: 6,
    overflow: "hidden",
  },
  kind: { color: colors.stamp, fontSize: 11, fontWeight: "800" },
  title: { color: colors.ink, fontWeight: "700", marginTop: 4, fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4, fontSize: 13 },
  cond: { color: colors.ink, marginTop: 8, lineHeight: 18, fontSize: 13 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 12, alignItems: "center" },
  btnOk: {
    backgroundColor: colors.stampOk,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  btnGhost: {
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.paper,
  },
  chat: { color: colors.ink, fontWeight: "800" },
  ok: { color: "#fff", fontWeight: "800" },
  no: { color: colors.stamp, fontWeight: "800" },
});
