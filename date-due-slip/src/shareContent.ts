import { Platform, Share } from "react-native";
import { getApiBase } from "./api";

export async function publicPostUrl(postId: number, commentId?: number) {
  const base = (await getApiBase()).replace(/\/$/, "");
  if (commentId != null) return `${base}/#post-${postId}-c${commentId}`;
  return `${base}/#post-${postId}`;
}

/** Opens OS share sheet (messengers, social, mail, SMS, Nearby Share, …). */
export async function shareContent(opts: {
  title: string;
  text: string;
  url: string;
}) {
  const title = (opts.title || "").trim() || "Реченець";
  const body = (opts.text || "").trim();
  const url = opts.url;
  const message = [title, body, url].filter(Boolean).join("\n\n");
  await Share.share(
    Platform.OS === "ios"
      ? { title, message: body ? `${title}\n\n${body}` : title, url }
      : { message, title }
  );
}

export async function sharePost(post: {
  id: number;
  title: string;
  text: string;
}) {
  const url = await publicPostUrl(post.id);
  await shareContent({
    title: post.title,
    text: post.text.slice(0, 280),
    url,
  });
}

export async function shareComment(opts: {
  postId: number;
  commentId: number;
  author: string;
  text: string;
  postTitle?: string;
}) {
  const url = await publicPostUrl(opts.postId, opts.commentId);
  await shareContent({
    title: opts.postTitle ? `Коментар · ${opts.postTitle}` : "Коментар · Реченець",
    text: `${opts.author}: ${opts.text}`.slice(0, 280),
    url,
  });
}
