import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, LibraryApi } from "../src/api";
import { CyrillicTextInput } from "../src/CyrillicTextInput";
import { colors, fs, s, btnRadius } from "../src/theme";
import type { LibraryOverlap, LibrarySnapshot } from "../src/types";

function emptyIsbnEdits(rows: LibraryOverlap[]): Record<string, string> {
  return Object.fromEntries((rows || []).map((r) => [r.isbn, ""]));
}

export default function SharedLibraryScreen() {
  const router = useRouter();
  const [snap, setSnap] = useState<LibrarySnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRedeem, setShowRedeem] = useState(false);
  const [mergeCode, setMergeCode] = useState("");
  const [mergeInviteId, setMergeInviteId] = useState<number | null>(null);
  const [mergeOverlap, setMergeOverlap] = useState<LibraryOverlap[]>([]);
  const [isbnEdits, setIsbnEdits] = useState<Record<string, string>>({});
  const [splitPick, setSplitPick] = useState<Record<number, boolean>>({});

  const load = useCallback(async () => {
    const data = await LibraryApi.mine();
    setSnap(data);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Бібліотека", e instanceof ApiError ? e.message : String(e)));
    }, [load])
  );

  if (!snap) return null;

  const generateCode = async () => {
    setBusy(true);
    try {
      const res = await LibraryApi.generateMergeCode();
      await load();
      Alert.alert(
        "Код об'єднання",
        `${res.code}\n\nДійсний ~${Math.max(1, Math.round(res.seconds_left / 60))} хв. Передайте іншому користувачу.`
      );
    } catch (e) {
      Alert.alert("Merge", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const redeemCode = async () => {
    const code = mergeCode.trim();
    if (!/^\d{4}$/.test(code)) {
      Alert.alert("Merge", "Введіть 4-цифровий код.");
      return;
    }
    setBusy(true);
    try {
      const res = await LibraryApi.redeemMergeCode(code);
      setMergeCode("");
      setShowRedeem(false);
      await load();
      if (res.awaiting_admin_isbn) {
        Alert.alert(
          "Об'єднання",
          res.detail ||
            "Код прийнято. Адміністратор підтвердить кількість спільних ISBN."
        );
        return;
      }
      Alert.alert("Об'єднання", "Готово. За потреби проголосуйте за адміна.");
    } catch (e) {
      Alert.alert("Merge", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const doAccept = async (inviteId: number) => {
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
      Alert.alert("Об'єднання", "Готово. За потреби проголосуйте за адміна.");
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
      Alert.alert("Об'єднання", e instanceof ApiError ? e.message : String(e));
    }
  };

  const confirmMerge = async () => {
    if (mergeInviteId == null) return;
    const counts: Record<string, number> = {};
    for (const row of mergeOverlap) {
      const raw = (isbnEdits[row.isbn] || "").trim();
      const n = parseInt(raw, 10);
      if (!Number.isFinite(n) || n < 1 || n > row.combined) {
        Alert.alert(
          "ISBN",
          `«${row.title}»: вкажіть кількість від 1 до ${row.combined}.`
        );
        return;
      }
      counts[row.isbn] = n;
    }
    try {
      await LibraryApi.confirmMergeIsbn(mergeInviteId, counts);
      setMergeInviteId(null);
      setMergeOverlap([]);
      setIsbnEdits({});
      await load();
      Alert.alert("Об'єднання", "Кількість підтверджено — бібліотеки об'єднано.");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const p = e.payload as { overlap?: LibraryOverlap[]; detail?: string };
        const ov = p.overlap || [];
        setMergeOverlap(ov);
        setIsbnEdits(emptyIsbnEdits(ov));
        Alert.alert("ISBN", p.detail || "Вкажіть кількість.");
        return;
      }
      Alert.alert("Об'єднання", e instanceof ApiError ? e.message : String(e));
    }
  };

  const el = snap.election;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h}>{snap.library.name}</Text>
      <Text style={styles.meta}>
        Адмін @{snap.library.admin_username}
        {snap.library.i_am_admin ? " (ви)" : ""} · {snap.library.member_count} учасн.
        {snap.library.is_shared ? " · об'єднана" : ""}
      </Text>
      {snap.members.map((m) => (
        <Text key={m.username} style={styles.row}>
          @{m.username} — {m.role}
        </Text>
      ))}

      <View style={styles.block}>
        <Text style={styles.h2}>Голосування за адміна</Text>
        {el ? (
          <>
            <Text style={styles.meta}>
              {el.reason} · {el.votes_cast}/{el.member_count}
            </Text>
            {el.candidates.map((c) => (
              <View key={c.user_id} style={styles.inviteRow}>
                <Text style={[styles.row, { flex: 1 }]}>
                  @{c.username} ({c.votes})
                  {c.is_current_admin ? " · поточний" : ""}
                  {el.my_candidate_id === c.user_id ? " · ваш голос" : ""}
                </Text>
                <Pressable
                  onPress={() =>
                    LibraryApi.voteElection(el.election_id, c.user_id)
                      .then(load)
                      .catch((e) =>
                        Alert.alert("Голос", e instanceof ApiError ? e.message : String(e))
                      )
                  }
                >
                  <Text style={styles.link}>
                    {el.my_candidate_id === c.user_id ? "✓" : "Голос"}
                  </Text>
                </Pressable>
              </View>
            ))}
            <View style={styles.rowBtns}>
              {el.can_finalize ? (
                <Pressable
                  style={styles.btn}
                  onPress={() =>
                    LibraryApi.finalizeElection(el.election_id)
                      .then(load)
                      .then(() => Alert.alert("Вибори", "Адміна обрано."))
                      .catch((e) =>
                        Alert.alert("Вибори", e instanceof ApiError ? e.message : String(e))
                      )
                  }
                >
                  <Text style={styles.btnText}>Завершити</Text>
                </Pressable>
              ) : null}
              <Pressable
                style={[styles.btn, styles.btnGhost]}
                onPress={() =>
                  LibraryApi.cancelElection(el.election_id)
                    .then(load)
                    .catch((e) =>
                      Alert.alert("Вибори", e instanceof ApiError ? e.message : String(e))
                    )
                }
              >
                <Text style={[styles.btnText, { color: colors.ink }]}>Скасувати</Text>
              </Pressable>
            </View>
          </>
        ) : snap.library.is_shared ? (
          <Pressable
            style={styles.btn}
            onPress={() =>
              LibraryApi.startElection()
                .then(load)
                .catch((e) =>
                  Alert.alert("Вибори", e instanceof ApiError ? e.message : String(e))
                )
            }
          >
            <Text style={styles.btnText}>Відкрити голосування</Text>
          </Pressable>
        ) : (
          <Text style={styles.meta}>Доступно після merge з іншим користувачем.</Text>
        )}
      </View>

      {snap.library.i_am_admin ? (
        <View style={styles.block}>
          <Text style={styles.h2}>Код об'єднання</Text>
          <Text style={styles.meta}>
            Згенеруйте 4-цифровий код (дійсний 5 хв) і передайте іншому користувачу.
          </Text>
          {snap.active_merge_code ? (
            <>
              <Text style={styles.code}>{snap.active_merge_code.code}</Text>
              <Text style={styles.meta}>
                залишилось ~{snap.active_merge_code.seconds_left} с
              </Text>
            </>
          ) : null}
          <Pressable
            style={[styles.btn, busy && { opacity: 0.6 }]}
            onPress={generateCode}
            disabled={busy}
          >
            <Text style={styles.btnText}>
              {snap.active_merge_code ? "Новий код" : "Згенерувати код"}
            </Text>
          </Pressable>
          {snap.invites_out.map((i) => (
            <View key={i.id} style={styles.inviteRow}>
              <Pressable
                onPress={() =>
                  i.to_user_id != null
                    ? router.push(`/chat/${i.to_user_id}`)
                    : undefined
                }
              >
                <Text style={styles.row}>
                  → @{i.to_username}
                  {i.status === "awaiting_isbn" ? " (ISBN)" : ""}
                </Text>
              </Pressable>
              <Pressable onPress={() => LibraryApi.cancelInvite(i.id).then(load)}>
                <Text style={styles.link}>Скасувати</Text>
              </Pressable>
            </View>
          ))}
        </View>
      ) : null}

      <View style={styles.block}>
        <Text style={styles.h2}>Об'єднати бібліотеку за кодом</Text>
        <Text style={styles.meta}>
          Натисніть Merge Library і введіть код адміністратора іншої бібліотеки.
        </Text>
        {!showRedeem ? (
          <Pressable style={styles.btn} onPress={() => setShowRedeem(true)}>
            <Text style={styles.btnText}>Merge Library</Text>
          </Pressable>
        ) : (
          <>
            <CyrillicTextInput
              style={[styles.input, { marginBottom: 8, letterSpacing: 4 }]}
              value={mergeCode}
              onChangeText={(t) => setMergeCode(t.replace(/\D/g, "").slice(0, 4))}
              placeholder="••••"
              placeholderTextColor={colors.muted}
              keyboardType="number-pad"
              maxLength={4}
              autoFocus
            />
            <View style={styles.rowBtns}>
              <Pressable
                style={[styles.btn, (busy || mergeCode.length !== 4) && { opacity: 0.6 }]}
                onPress={redeemCode}
                disabled={busy || mergeCode.length !== 4}
              >
                <Text style={styles.btnText}>Підтвердити код</Text>
              </Pressable>
              <Pressable
                style={[styles.btn, styles.btnGhost]}
                onPress={() => {
                  setShowRedeem(false);
                  setMergeCode("");
                }}
              >
                <Text style={[styles.btnText, { color: colors.ink }]}>Скасувати</Text>
              </Pressable>
            </View>
          </>
        )}
      </View>

      {(snap.awaiting_isbn_merges || []).length > 0 ||
      (mergeOverlap.length > 0 && mergeInviteId != null) ? (
        <View style={styles.block}>
          <Text style={styles.h2}>Підтвердіть кількість ISBN (адмін)</Text>
          <Text style={styles.warn}>
            Вкажіть реальну кількість фізичних примірників для дубльованих ISBN.
          </Text>
          {(snap.awaiting_isbn_merges || []).map((inv) => (
            <Pressable
              key={inv.id}
              style={{ marginBottom: 8 }}
              onPress={() => {
                setMergeInviteId(inv.id);
                setMergeOverlap(inv.overlap || []);
                setIsbnEdits(emptyIsbnEdits(inv.overlap || []));
              }}
            >
              <Text style={styles.link}>
                Merge з @{inv.to_username}
                {mergeInviteId === inv.id ? " · обрано" : " · відкрити форму"}
              </Text>
            </Pressable>
          ))}
          {mergeOverlap.length > 0 && mergeInviteId != null
            ? mergeOverlap.map((row) => (
                <View key={row.isbn} style={{ marginBottom: 10 }}>
                  <Text style={styles.row}>
                    {row.title} (ISBN {row.isbn}) — у вас {row.target_count} + у них{" "}
                    {row.source_count} = {row.combined} у базі
                  </Text>
                  <CyrillicTextInput
                    style={styles.input}
                    value={isbnEdits[row.isbn] || ""}
                    onChangeText={(t) =>
                      setIsbnEdits((prev) => ({ ...prev, [row.isbn]: t }))
                    }
                    keyboardType="number-pad"
                    placeholder={`1…${row.combined}`}
                  />
                </View>
              ))
            : null}
          {mergeInviteId != null ? (
            <Pressable style={styles.btn} onPress={confirmMerge}>
              <Text style={styles.btnText}>Підтвердити кількість і об'єднати</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      {snap.invites_in.map((i) => (
        <View key={i.id} style={styles.block}>
          <Text style={styles.h2}>Запрошення від @{i.from_username}</Text>
          <Text style={styles.meta}>{i.library_name}</Text>
          {i.from_user_id != null ? (
            <Pressable onPress={() => router.push(`/chat/${i.from_user_id}`)}>
              <Text style={styles.link}>Відповісти в чаті</Text>
            </Pressable>
          ) : null}
          {i.overlap?.length ? (
            <Text style={styles.warn}>
              Спільних ISBN: {i.overlap.length} — після згоди адмін підтвердить кількість
            </Text>
          ) : null}
          <View style={styles.rowBtns}>
            <Pressable style={styles.btn} onPress={() => doAccept(i.id)}>
              <Text style={styles.btnText}>Прийняти</Text>
            </Pressable>
            <Pressable
              style={[styles.btn, styles.btnGhost]}
              onPress={() => LibraryApi.rejectInvite(i.id).then(load)}
            >
              <Text style={[styles.btnText, { color: colors.ink }]}>Відхилити</Text>
            </Pressable>
          </View>
        </View>
      ))}

      {snap.pending_actions.map((a) => (
        <View key={a.id} style={styles.block}>
          <Text style={styles.h2}>
            {a.action_type_label} · @{a.initiator_username}
          </Text>
          <Text style={styles.meta}>{JSON.stringify(a.payload)}</Text>
          {snap.library.i_am_admin ? (
            <View style={styles.rowBtns}>
              <Pressable
                style={styles.btn}
                onPress={() => LibraryApi.resolveAction(a.id, true).then(load)}
              >
                <Text style={styles.btnText}>Схвалити</Text>
              </Pressable>
              <Pressable
                style={[styles.btn, styles.btnGhost]}
                onPress={() => LibraryApi.resolveAction(a.id, false).then(load)}
              >
                <Text style={[styles.btnText, { color: colors.ink }]}>Відхилити</Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      ))}

      {!snap.library.i_am_admin ? (
        <View style={styles.block}>
          <Text style={styles.h2}>Поділ / вихід</Text>
          <Text style={styles.meta}>Оберіть примірники, які забираєте:</Text>
          {(snap.splittable_copies || []).map((c) => (
            <Pressable
              key={c.id}
              style={styles.checkRow}
              onPress={() =>
                setSplitPick((prev) => ({ ...prev, [c.id]: !prev[c.id] }))
              }
            >
              <Text style={styles.row}>
                {splitPick[c.id] ? "☑" : "☐"} {c.title} · #{c.id}
                {c.added_by_me ? " (ви додали)" : ""}
              </Text>
            </Pressable>
          ))}
          <Pressable
            style={[styles.btn, { backgroundColor: colors.stamp, marginTop: 12 }]}
            onPress={() => {
              const ids = Object.entries(splitPick)
                .filter(([, on]) => on)
                .map(([id]) => Number(id));
              Alert.alert(
                "Поділ",
                ids.length
                  ? `Запит на вихід з ${ids.length} примірник(ами)?`
                  : "Вийти без примірників?",
                [
                  { text: "Скасувати", style: "cancel" },
                  {
                    text: "Надіслати",
                    onPress: async () => {
                      try {
                        const r = await LibraryApi.splitLeave(ids);
                        Alert.alert(
                          "Вихід",
                          r.pending_approval ? "Очікує адміна." : "Готово."
                        );
                        setSplitPick({});
                        await load();
                      } catch (e) {
                        Alert.alert(
                          "Вихід",
                          e instanceof ApiError ? e.message : String(e)
                        );
                      }
                    },
                  },
                ]
              );
            }}
          >
            <Text style={styles.btnText}>Запит на поділ</Text>
          </Pressable>
        </View>
      ) : snap.library.is_shared ? (
        <View style={styles.block}>
          <Text style={styles.h2}>Поділ (адмін)</Text>
          <Text style={styles.meta}>
            Спочатку оберіть іншого адміна голосуванням — після зміни ролі зможете вийти з поділом.
          </Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: fs(22), fontWeight: "800", color: colors.ink },
  h2: { fontSize: fs(16), fontWeight: "800", color: colors.ink, marginBottom: 6 },
  meta: { color: colors.muted, fontSize: fs(13), marginTop: 4, marginBottom: 8 },
  row: { color: colors.ink, fontSize: fs(15), marginTop: 4 },
  warn: { color: colors.stamp, fontSize: fs(13), marginVertical: 6 },
  block: {
    marginTop: s(16),
    paddingTop: s(12),
    borderTopWidth: 1,
    borderColor: colors.line,
  },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    fontSize: fs(16),
  },
  btn: {
    backgroundColor: colors.ink,
    padding: s(12),
    marginTop: s(10),
    borderRadius: btnRadius,
    minHeight: s(48),
    justifyContent: "center",
    flex: 1,
  },
  btnGhost: { backgroundColor: colors.paperDark },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(15) },
  rowBtns: { flexDirection: "row", gap: 10 },
  inviteRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 10 },
  link: { color: colors.stamp, fontWeight: "700", paddingHorizontal: 8 },
  checkRow: { paddingVertical: 6 },
  code: {
    fontSize: fs(36),
    fontWeight: "800",
    letterSpacing: 8,
    color: colors.ink,
    marginTop: 8,
    marginBottom: 4,
    fontVariant: ["tabular-nums"],
  },
});
