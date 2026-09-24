export type User = {
  id: number;
  username: string;
  email?: string;
  biography: string;
  avatar_url: string | null;
  last_watched_post_id?: number | null;
};

export type Book = {
  id: number;
  isbn: string;
  title: string;
  authors: string;
  publisher: string;
  publish_date: string;
  cover_url: string;
  info_url: string;
  min_readers_age: number;
  max_readers_age: number;
  reader_age_summary: string;
};

export type Shelf = {
  id: number;
  user: User;
  book: Book;
  /** Physical copy id — same ISBN can have many copies. */
  copy_id?: number | null;
  borrowed_from: User | null;
  /** When this is your owned copy currently lent out. */
  lent_to?: User | null;
  return_pending: boolean;
  due_date: string | null;
  /** Due date from the active loan row (owned + lent out). */
  loan_due_date?: string | null;
  is_overdue: boolean;
  days_left: number | null;
  is_lent_out?: boolean;
  /** Id рядка позичальника з return_pending — для кнопки підтвердження у власника. */
  pending_return_shelf_id?: number | null;
  /** Id полиці власника для ExchangeApi.create (для позики на чужій полиці). */
  request_shelf_id?: number | null;
  added_at: string;
};

export type BookCopyDetail = {
  id: number;
  book: Book;
  owner: User;
  created_at: string;
};

export type CopyEvent = {
  id: number;
  code: string;
  code_display: string;
  actor: User | null;
  holder: User | null;
  legal_owner: User | null;
  previous_holder: User | null;
  previous_owner: User | null;
  counterparty: User | null;
  exchange_request_id: number | null;
  created_at: string;
};

/** Browse card: one cover per ISBN, owners listed inline. */
export type BookBrowseGroup = {
  book: Book;
  owners: User[];
  copies: Shelf[];
};

export type Comment = {
  id: number;
  author: User;
  text: string;
  created_at: string;
};

export type Post = {
  id: number;
  author: User;
  book: Book | null;
  title: string;
  text: string;
  created_ad: string;
  likes_count: number;
  comments_count: number;
  liked_by_me: boolean;
  comments: Comment[];
};

export type Exchange = {
  id: number;
  requester: User;
  shelf_owner: User;
  target_shelf: Shelf;
  offer_shelf: Shelf | null;
  status: string;
  kind: "borrow" | "exchange";
  /** Pending borrow while copy is lent — accepting transmits to requester. */
  is_transmission?: boolean;
  created_at: string;
  resolved_at: string | null;
};

export type QueueEntry = {
  id: number;
  user_id: number;
  username: string;
  status: string;
  position: number;
  exchange_request_id: number | null;
  created_at: string;
};

export type LoanHandoff = {
  id: number;
  copy_id: number;
  book_title: string;
  owner: User;
  from_user: User;
  to_user: User;
  status: "awaiting_give" | "awaiting_receive" | "completed" | "cancelled";
  giver_confirmed_at: string | null;
  receiver_confirmed_at: string | null;
  exchange_request_id: number | null;
  created_at: string;
  my_role: "owner" | "giver" | "receiver" | null;
  can_confirm_give: boolean;
  can_confirm_receive: boolean;
  can_cancel: boolean;
  participants: User[];
};

export type Message = {
  id: number;
  sender: User;
  recipient: User;
  body: string;
  exchange_request: number | null;
  created_at: string;
  read_at: string | null;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
