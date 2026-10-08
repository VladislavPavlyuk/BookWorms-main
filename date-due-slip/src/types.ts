export type UserSubProfile = {
  id: number;
  name: string;
  age: number | null;
  place: string;
  preferred_subjects: string[];
  sort_order?: number;
  created_at?: string;
};

export type User = {
  id: number;
  username: string;
  email?: string;
  biography: string;
  avatar_url: string | null;
  age?: number | null;
  place?: string;
  preferred_subjects?: string[];
  subprofiles?: UserSubProfile[];
  last_watched_post_id?: number | null;
};

export type BookOtherIsbn = { isbn: string; binding?: string };

export type Book = {
  id: number;
  isbn: string;
  isbn10?: string;
  title: string;
  title_long?: string;
  authors: string;
  publisher: string;
  publish_date: string;
  binding?: string;
  language?: string;
  edition?: string;
  pages?: number | null;
  dimensions?: string;
  dimensions_data?: Record<string, unknown> | unknown[];
  dewey_decimal?: string[];
  overview?: string;
  synopsis?: string;
  excerpt?: string;
  msrp?: string | null;
  subjects?: string[];
  other_isbns?: BookOtherIsbn[];
  cover_url: string;
  cover_url_original?: string;
  info_url: string;
  catalog_source?: string;
  /** Full OCR text from cover photo (AI). */
  cover_text?: string;
  photo_urls?: string[];
  min_readers_age: number;
  max_readers_age: number;
  reader_age_summary: string;
  /** Local 9799… code — no catalog ISBN on the cover. */
  isbn_missing?: boolean;
  note?: string;
};

export type BookPriceQuote = {
  source_name: string;
  source_url: string;
  price: string;
  currency: string;
  price_uah: string;
};

export type BookPriceEval = {
  status: "pending" | "ready" | "missing" | "error" | string;
  currency: string;
  price_avg: string | null;
  price_min: string | null;
  price_max: string | null;
  source_count: number;
  evaluated_at: string | null;
  last_error?: string;
  quotes: BookPriceQuote[];
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
  /** Sole-owned manual/local book — can PATCH /shelf/{id}/manual/ */
  can_edit_manual?: boolean;
  /** ISBN market price eval — only on owner's library. */
  price_eval?: BookPriceEval | null;
  /** Owner listing flags on this physical copy (multi-select). */
  is_fee_sharing?: boolean;
  is_hidden?: boolean;
  is_for_sale?: boolean;
  is_for_rent?: boolean;
  is_as_gift?: boolean;
  is_for_exchange?: boolean;
  is_free_of_deposit?: boolean;
  listing_labels?: string[];
  sale_gift?: "" | "for_sale" | "as_gift" | string;
  sale_price?: string | null;
  rent_price_per_day?: string | null;
  requires_deposit?: boolean;
  is_publicly_listed?: boolean;
  listing_status_display?: string | null;
  library_owners?: User[];
  owners_label?: string | null;
  /** Bound QR → confirm return/receive must scan the label. */
  requires_qr_scan?: boolean;
  added_at: string;
};

export type SaleGift = "" | "for_sale" | "as_gift";

export const LISTING_CHECKBOX_OPTIONS: { key: keyof Shelf; label: string }[] = [
  { key: "is_fee_sharing", label: "Free sharing " },
  { key: "is_hidden", label: "Hidden" },
  { key: "is_for_rent", label: "For rent" },
  { key: "is_for_exchange", label: "For exchange" },
  { key: "is_free_of_deposit", label: "Free of deposit" },
];

export const SALE_GIFT_OPTIONS: { value: SaleGift; label: string }[] = [
  { value: "", label: "Neither" },
  { value: "for_sale", label: "For sale" },
  { value: "as_gift", label: "As a gift" },
];

export type BookCopyDetail = {
  id: number;
  book: Book;
  owner: User;
  created_at: string;
  has_qr?: boolean;
  qr_attached?: boolean;
  qr_attached_at?: string | null;
  requires_qr_scan?: boolean;
  /** Owner-only: BW1.<token> for display/print. */
  qr_payload?: string | null;
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
  owners_label?: string;
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
  /** Requester allows owner to pick a book from requester's library. */
  offer_open?: boolean;
  status: string;
  kind: "borrow" | "exchange" | "borrow_open_exchange";
  /** Pending borrow while copy is lent — accepting transmits to requester. */
  is_transmission?: boolean;
  /** Requester's proposed return date (YYYY-MM-DD) for borrow/transmit. */
  proposed_due_date?: string | null;
  due_date_proposer?: "requester" | "owner" | string;
  due_date_confirmed?: boolean;
  can_propose_due?: boolean;
  can_confirm_due?: boolean;
  can_pick_offer?: boolean;
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
  requires_qr_scan?: boolean;
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
  exchange_request_detail: {
    id: number;
    status: string;
    kind: "exchange" | "loan" | "borrow_open_exchange";
    offer_open?: boolean;
    is_transmission: boolean;
    book_title: string;
    proposed_due_date?: string | null;
    due_date_proposer?: "requester" | "owner" | string;
    due_date_confirmed?: boolean;
    can_accept: boolean;
    can_reject: boolean;
    can_cancel: boolean;
    can_pick_offer?: boolean;
    can_propose_due?: boolean;
    can_confirm_due?: boolean;
  } | null;
  library_invite: {
    id: number;
    status: string;
    library_name: string;
    message: string;
    can_respond: boolean;
    can_cancel: boolean;
    overlap: {
      isbn: string;
      title: string;
      combined: number;
      target_count: number;
      source_count: number;
    }[] | null;
  } | null;
  library_action: {
    id: number;
    status: string;
    action_type: string;
    action_type_label?: string;
    title: string;
    isbn: string;
    existing_count: number;
    count?: number;
    can_decide: boolean;
    initiator_username: string;
  } | null;
  created_at: string;
  read_at: string | null;
  is_system?: boolean;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type LibraryOverlap = {
  isbn: string;
  title: string;
  combined: number;
  target_count: number;
  source_count: number;
  book_id?: number;
};

export type LibraryElection = {
  election_id: number;
  status: string;
  reason: string;
  member_count: number;
  votes_cast: number;
  can_finalize: boolean;
  i_voted?: boolean;
  my_candidate_id?: number | null;
  candidates: {
    user_id: number;
    username: string;
    votes: number;
    is_current_admin: boolean;
  }[];
};

/** GET /api/library/ snapshot for shared-library screen. */
export type LibrarySnapshot = {
  library: {
    id: number;
    name: string;
    admin_username: string;
    i_am_admin: boolean;
    member_count: number;
    is_shared?: boolean;
  };
  members: { username: string; role: string; user_id?: number }[];
  invites_in: {
    id: number;
    from_user_id?: number;
    from_username: string;
    library_name: string;
    message: string;
    overlap: LibraryOverlap[];
  }[];
  invites_out: {
    id: number;
    to_user_id?: number;
    to_username: string;
    status?: string;
  }[];
  awaiting_isbn_merges?: {
    id: number;
    to_user_id: number;
    to_username: string;
    overlap: LibraryOverlap[];
  }[];
  merge_candidates?: { id: number; username: string; invite_pending: boolean }[];
  active_merge_code?: {
    code: string;
    expires_at: string;
    seconds_left: number;
    ttl_seconds: number;
  } | null;
  pending_actions: {
    id: number;
    action_type: string;
    action_type_label: string;
    initiator_username: string;
    payload: Record<string, unknown>;
  }[];
  election: LibraryElection | null;
  splittable_copies: {
    id: number;
    title: string;
    isbn: string;
    added_by_me: boolean;
    held_by_me: boolean;
  }[];
};
