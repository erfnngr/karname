import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChatTarget, onChatTarget, request } from './bridge';
import { useRoomDrafts } from './useRoomDrafts';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Archive,
  AtSign,
  Bell,
  BellOff,
  Bookmark,
  Calendar,
  Check,
  CheckCheck,
  CheckSquare,
  Clock,
  Download,
  Eye,
  FileText,
  Forward,
  Heart,
  Image as ImageIcon,
  ListFilter,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Pin,
  RefreshCw,
  Reply,
  RotateCcw,
  Search,
  Send,
  Smile,
  SquarePen,
  Trash2,
  Users,
  Vote,
  X,
} from 'lucide-react';

type Room = {
  company: string;
  room: string;
  title: string;
  label?: string;
  display_title?: string;
  company_name?: string;
  avatar?: string;
  unread?: number;
  muted?: boolean;
  direct?: boolean;
  saved?: boolean;
  last?: { text?: string; created?: string };
};

type Message = {
  seq: number;
  id: string;
  author?: string;
  thread_root?: string;
  reply_count?: number;
  seen_by?: { fullname: string }[];
  likes?: { fullname: string }[];
  text: string;
  created: string;
  person?: { fullname?: string; avatar?: string; color?: string };
  files?: { id: string; name: string; size?: number; mime?: string }[];
  deleted?: boolean;
  can_delete?: boolean;
  saved?: boolean;
  pinned?: boolean;
  reply_excerpt?: string;
  kind?: string;
  payload?: { at?: string; location?: string; options?: string[] };
  votes?: number[];
  my_vote?: number | null;
};

type Thread = {
  items: Message[];
  has_more: boolean;
  members?: { id: string; fullname: string }[];
};

type Person = { id: string; fullname: string; username: string };
type Attachment = { name: string; data: string; size: number };
type Scheduled = { id: string; text: string; due_at: string; status: string; file_names: string[]; error?: string };
type Queued = { id: string; text: string; company: string; room: string; status: string; error: string };
type RoomFilter = 'all' | 'unread' | 'saved' | 'direct' | 'group' | 'drafts';

const NO_FILES: Attachment[] = [];
const EMOJIS = '😀 😃 😄 😁 😊 🙂 😉 😍 🥰 😎 🤔 😅 😂 🙏 👍 👎 👏 💪 ✅ ❌ ❤️ 💙 💚 💜 🎉 🎯 📌 📎 📅 🕒 💼 📊 📝 ☕ 🌹'.split(' ');

const roomDisplayName = (r: Room) => r.label || r.display_title || r.title;
const isImageName = (name: string) => /\.(png|jpe?g|webp|gif)$/i.test(name);
const formatBytes = (bytes?: number) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes.toLocaleString('fa-IR')} بایت`;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString('fa-IR')} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} مگابایت`;
};

const formatTehranTime = (iso?: string) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tehran' });
  } catch {
    return '';
  }
};

const formatTehranDateTime = (iso?: string) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('fa-IR', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Asia/Tehran',
    });
  } catch {
    return iso;
  }
};

export function LiveChat() {
  const [userId, setUserId] = useState('');
  const [todayJalali, setTodayJalali] = useState('1405/01/01');
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selected, setSelected] = useState<Room | null>(null);
  const [roomFilter, setRoomFilter] = useState<RoomFilter>('all');
  const [search, setSearch] = useState('');

  const composeRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [emojiOpen, setEmojiOpen] = useState(false);
  const [mentionPeople, setMentionPeople] = useState<Person[] | null>(null);
  const [membersList, setMembersList] = useState<{ id: string; fullname: string }[]>([]);
  const [showMembers, setShowMembers] = useState(false);
  const [seenModal, setSeenModal] = useState<Message | null>(null);
  const [imagePreview, setImagePreview] = useState<{ name: string; url: string; id: string } | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [showMessageSearch, setShowMessageSearch] = useState(false);
  const [messageSearch, setMessageSearch] = useState('');
  const [messageFilter, setMessageFilter] = useState<'all' | 'saved' | 'pinned'>('all');
  const [thread, setThread] = useState('');
  const threadRef = useRef(thread);
  threadRef.current = thread;

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [roomFiles, setRoomFiles] = useState<Record<string, Attachment[]>>({});
  const roomKey = selected ? JSON.stringify([selected.company, selected.room]) : '';
  const draft = drafts[roomKey] || '';
  const files = roomFiles[roomKey] || NO_FILES;

  const [error, setError] = useState('');
  const [infoToast, setInfoToast] = useState('');
  const [busy, setBusy] = useState(false);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const pendingSend = useRef<{ key: string; id: string } | null>(null);

  const messageOwner = useRef('');
  const lastRead = useRef('');
  const reading = useRef(false);
  const filterRef = useRef(messageFilter);
  filterRef.current = messageFilter;
  const searchRef = useRef(messageSearch);
  searchRef.current = messageSearch;
  const messageList = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const historyLoaded = useRef(false);
  const scrollRestore = useRef<{ height: number; top: number } | null>(null);

  const [queue, setQueue] = useState<Queued[]>([]);
  const [showQueue, setShowQueue] = useState(false);
  const [cancelQueued, setCancelQueued] = useState<Queued | null>(null);
  const flushing = useRef(false);

  const [companies, setCompanies] = useState<{ id: string; name: string }[]>([]);
  const [createMode, setCreateMode] = useState<'direct' | 'group' | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [members, setMembers] = useState<string[]>([]);
  const [groupName, setGroupName] = useState('');
  const [groupCompany, setGroupCompany] = useState('');
  const [groupAvatar, setGroupAvatar] = useState('');
  const groupAttempt = useRef<{ key: string; id: string } | null>(null);

  const [restoreOpen, setRestoreOpen] = useState(false);
  const [clearConfirm, setClearConfirm] = useState<{ room: Room; count: number; through: number } | null>(null);
  const [hideRoom, setHideRoom] = useState<Room | null>(null);

  const specialAttempt = useRef<{ key: string; id: string } | null>(null);
  const [pollModal, setPollModal] = useState<{ title: string; optionsText: string } | null>(null);
  const [meetingModal, setMeetingModal] = useState<{ title: string; date: string; time: string; location: string } | null>(null);
  const [scheduleModal, setScheduleModal] = useState<{ date: string; time: string } | null>(null);

  const scheduleAttempt = useRef<{ key: string; id: string } | null>(null);
  const [scheduled, setScheduled] = useState<Scheduled[] | null>(null);
  const [cancelSchedule, setCancelSchedule] = useState<Scheduled | null>(null);

  const [replyByRoom, setReplyByRoom] = useState<Record<string, Message | undefined>>({});
  const reply = replyByRoom[roomKey];
  const [confirmDelete, setConfirmDelete] = useState<Message | null>(null);
  const [forwarding, setForwarding] = useState<Message | null>(null);
  const forwardAttempt = useRef<{ key: string; id: string } | null>(null);
  const pendingTargetRef = useRef<ChatTarget | null>(null);

  const persisted = useRoomDrafts(
    selected,
    roomKey,
    selected ? { company: selected.company, room: selected.room, text: draft, files, reply_to: reply?.id || null } : null,
    (key, value) => {
      setDrafts((current) => ({ ...current, [key]: value.text || '' }));
      setRoomFiles((current) => ({ ...current, [key]: value.files || NO_FILES }));
      if (value.reply_to) {
        setReplyByRoom((current) => ({ ...current, [key]: { id: value.reply_to!, seq: 0, text: 'پیام قبلی', created: '' } }));
      }
    },
    setError
  );

  const refresh = async (): Promise<Room[]> => {
    try {
      const value = await request<Room[]>('rooms');
      setRooms(value);
      return value;
    } catch (e) {
      setError(String(e));
      return [];
    }
  };

  const applyTarget = (target: ChatTarget, currentRooms: Room[]) => {
    const match = currentRooms.find((r) => r.company === target.company && r.room === target.room);
    if (match) {
      setMessageSearch('');
      setMessageFilter('all');
      setThread(target.thread || '');
      setSelected(match);
      pendingTargetRef.current = null;
    } else {
      pendingTargetRef.current = target;
    }
  };

  useEffect(() => {
    return onChatTarget((target) => {
      if (!target.company || !target.room) return;
      void refresh().then((list) => applyTarget(target, list));
    });
  }, []);

  useEffect(() => {
    if (pendingTargetRef.current && rooms.length) {
      applyTarget(pendingTargetRef.current, rooms);
    }
  }, [rooms]);

  const mergePage = (items: Message[]) =>
    setMessages((current) => {
      const byId = new Map(current.map((m) => [m.id, m]));
      items.forEach((m) => byId.set(m.id, m));
      return [...byId.values()].sort((a, b) => a.seq - b.seq);
    });

  const refreshMessages = async (target: Room, before?: number) => {
    const query = searchRef.current;
    const filter = filterRef.current;
    const activeThread = threadRef.current;
    const value = await request<Thread>('messages', {
      company: target.company,
      room: target.room,
      ...(query.trim() ? { q: query.trim() } : {}),
      ...(filter === 'all' ? {} : { [filter]: '1' }),
      ...(activeThread ? { thread: activeThread } : {}),
      ...(before ? { before } : {}),
    });
    if (
      selectedRef.current?.company === target.company &&
      selectedRef.current?.room === target.room &&
      searchRef.current === query &&
      filterRef.current === filter &&
      threadRef.current === activeThread
    ) {
      mergePage(value.items);
    }
  };

  const refreshQueue = async () => {
    try {
      setQueue(await request<Queued[]>('queue_list'));
    } catch (e) {
      setError(String(e));
    }
  };

  const flushQueue = async () => {
    if (flushing.current) return;
    flushing.current = true;
    try {
      const result = await request<{ status: string; error?: string }>('queue_flush');
      await refreshQueue();
      if (result.status === 'needs_review') setError(result.error || 'پیام نیاز به بررسی دارد.');
      if (result.status === 'sent') {
        const target = selectedRef.current;
        if (target) await refreshMessages(target);
        void refresh();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      flushing.current = false;
    }
  };

  const queueAction = async (item: Queued, action: 'queue_retry' | 'queue_cancel') => {
    try {
      await request(action, { id: item.id });
      setCancelQueued(null);
      await refreshQueue();
      if (action === 'queue_retry') void flushQueue();
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    void request<{ id: string; fullname?: string; today_jalali?: string }>('identity')
      .then((user) => {
        setUserId(user.id);
        if (user.today_jalali) setTodayJalali(user.today_jalali);
      })
      .catch((e) => setError(String(e)));
    void refresh().then((list) => {
      if (!selectedRef.current && list.length && !pendingTargetRef.current) {
        setSelected(list[0]);
      }
    });
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void refreshQueue();
    void flushQueue();
    const timer = window.setInterval(() => void flushQueue(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const startCreate = async (mode: 'direct' | 'group') => {
    try {
      const [availablePeople, availableCompanies] = await Promise.all([
        request<Person[]>(mode === 'direct' ? 'people' : 'group_people', { company: '__shared_chat__' }),
        mode === 'group' ? request<{ id: string; name: string }[]>('companies') : Promise.resolve([]),
      ]);
      setPeople(availablePeople);
      setCompanies(availableCompanies);
      setMembers([]);
      setGroupName('');
      setGroupCompany('');
      setGroupAvatar('');
      setCreateMode(mode);
      setError('');
    } catch (e) {
      setError(String(e));
    }
  };

  const chooseAvatar = (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith('image/') || file.size > 8 * 1024 * 1024) {
      setError('یک تصویر معتبر تا حجم ۸ مگابایت انتخاب کنید.');
      return;
    }
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      try {
        const scale = Math.min(1, 256 / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext('2d');
        if (!context) throw Error('تصویر قابل پردازش نیست.');
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const encoded = canvas.toDataURL('image/png').split(',')[1];
        if (encoded.length > 400000) throw Error('تصویر گروه بیش از حد بزرگ است.');
        setGroupAvatar(encoded);
      } catch (e) {
        setError(String(e));
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      setError('تصویر قابل خواندن نیست.');
    };
    image.src = url;
  };

  const openSaved = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const room = await request<Room>('saved_chat', {});
      await refresh();
      setMessageSearch('');
      setMessageFilter('all');
      setThread('');
      setSelected(room);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const openDirect = async (person: string) => {
    if (busy) return;
    setBusy(true);
    try {
      const room = await request<Room>('direct', { company: '__shared_chat__', person });
      await refresh();
      setThread('');
      setMessageSearch('');
      setSelected(room);
      setCreateMode(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const createGroup = async () => {
    if (!groupName.trim() || busy) return;
    setBusy(true);
    const title = groupName.trim();
    const key = JSON.stringify([title, [...members].sort(), groupCompany, groupAvatar]);
    if (groupAttempt.current?.key !== key) {
      groupAttempt.current = { key, id: crypto.randomUUID().replaceAll('-', '') };
    }
    try {
      const room = await request<Room>('group', {
        company: '__shared_chat__',
        title,
        members,
        company_name: groupCompany.trim(),
        avatar: groupAvatar,
        request_id: groupAttempt.current.id,
      });
      const updated = await request<Room[]>('rooms');
      setRooms(updated);
      setThread('');
      setMessageSearch('');
      setSelected(updated.find((r) => r.company === room.company && r.room === room.room) || null);
      groupAttempt.current = null;
      setCreateMode(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const restoreDefaultGroup = async (roomId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await request('restore_group', { company: '__shared_chat__', room: roomId });
      setRestoreOpen(false);
      setInfoToast('گروه بازیابی شد.');
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const startClearRoom = async () => {
    if (!selected || busy) return;
    const target = selected;
    setBusy(true);
    try {
      const preview = await request<{ count: number; through: number }>('clear_room', {
        company: target.company,
        room: target.room,
      });
      if (!preview.count) {
        setInfoToast('پیامی برای پاک‌کردن وجود ندارد.');
      } else {
        setClearConfirm({ room: target, count: preview.count, through: preview.through });
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const confirmClearRoom = async () => {
    if (!clearConfirm || busy) return;
    setBusy(true);
    try {
      const res = await request<{ count: number }>('clear_room', {
        company: clearConfirm.room.company,
        room: clearConfirm.room.room,
        through: clearConfirm.through,
      });
      setClearConfirm(null);
      setInfoToast(`${res.count.toLocaleString('fa-IR')} پیام پاک شد.`);
      setMessages([]);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let active = true;
    let inFlight = false;
    let timer: number | undefined;
    followLatest.current = true;
    historyLoaded.current = false;
    messageOwner.current = '';
    setHasMore(false);
    setMessages([]);
    const poll = async () => {
      if (!selected || !active || inFlight) return;
      inFlight = true;
      try {
        const value = await request<Thread>('messages', {
          company: selected.company,
          room: selected.room,
          ...(messageSearch.trim() ? { q: messageSearch.trim() } : {}),
          ...(messageFilter === 'all' ? {} : { [messageFilter]: '1' }),
          ...(thread ? { thread } : {}),
        });
        if (active) {
          messageOwner.current = JSON.stringify([selected.company, selected.room, messageSearch]);
          setMembersList(value.members || []);
          setMessages((current) => {
            const older = historyLoaded.current && value.items.length ? current.filter((m) => m.seq < value.items[0].seq) : [];
            const merged = [...older, ...value.items];
            return JSON.stringify(current) === JSON.stringify(merged) ? current : merged;
          });
          if (!historyLoaded.current) setHasMore(value.has_more);
        }
      } catch (e) {
        if (active) setError(String(e));
      } finally {
        inFlight = false;
        if (active) timer = window.setTimeout(poll, 5000);
      }
    };
    if (selected) timer = window.setTimeout(poll, messageSearch ? 300 : 0);
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [selected?.company, selected?.room, messageSearch, messageFilter, thread]);

  React.useLayoutEffect(() => {
    const el = messageList.current;
    if (!el) return;
    if (scrollRestore.current) {
      el.scrollTop = scrollRestore.current.top + el.scrollHeight - scrollRestore.current.height;
      scrollRestore.current = null;
    } else if (followLatest.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  const confirmHide = async () => {
    if (!hideRoom || busy) return;
    const target = hideRoom;
    setBusy(true);
    try {
      await request('hide_room', { company: target.company, room: target.room });
      setHideRoom(null);
      if (selectedRef.current?.company === target.company && selectedRef.current?.room === target.room) {
        setSelected(null);
        setThread('');
        setMessages([]);
      }
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const insertEmoji = (emoji: string) => {
    if (!selected || !persisted.ready) return;
    const key = roomKey;
    const el = composeRef.current;
    const start = el?.selectionStart ?? draft.length;
    const end = el?.selectionEnd ?? start;
    persisted.markEdited(key);
    setDrafts((current) => {
      const text = current[key] || '';
      return { ...current, [key]: text.slice(0, start) + emoji + text.slice(end) };
    });
    setEmojiOpen(false);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + emoji.length, start + emoji.length);
    });
  };

  const chooseMention = async () => {
    if (!selected || !persisted.ready) return;
    const target = selected;
    try {
      const list = await request<Person[]>('group_people', { company: target.company });
      if (selectedRef.current?.company === target.company && selectedRef.current?.room === target.room) {
        const ids = new Set(membersList.map((m) => m.id));
        setMentionPeople(list.filter((p) => ids.has(p.id)));
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const insertMention = (person: Person) => {
    if (!selected || !persisted.ready) return;
    const key = roomKey;
    persisted.markEdited(key);
    setDrafts((current) => ({
      ...current,
      [key]: (current[key] || '') + ((current[key] || '').endsWith(' ') || !current[key] ? '' : ' ') + '@' + person.username + ' ',
    }));
    setMentionPeople(null);
    requestAnimationFrame(() => composeRef.current?.focus());
  };

  const toggleMute = async () => {
    if (!selected || busy) return;
    const target = selected;
    setBusy(true);
    try {
      await request('state', { company: target.company, room: target.room, muted: !target.muted });
      setSelected((current) =>
        current && current.company === target.company && current.room === target.room ? { ...current, muted: !target.muted } : current
      );
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const markRead = async () => {
    const room = selectedRef.current;
    const el = messageList.current;
    if (
      !room ||
      messageOwner.current !== JSON.stringify([room.company, room.room, searchRef.current]) ||
      !el ||
      !document.hasFocus() ||
      document.hidden ||
      el.scrollHeight - el.scrollTop - el.clientHeight >= 80 ||
      searchRef.current ||
      filterRef.current !== 'all' ||
      threadRef.current ||
      reading.current ||
      !messages.length
    ) {
      return;
    }
    const seq = messages[messages.length - 1].seq;
    const key = JSON.stringify([room.company, room.room, seq]);
    if (!seq || key === lastRead.current) return;
    reading.current = true;
    try {
      await request('state', { company: room.company, room: room.room, seq });
      lastRead.current = key;
      void refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      reading.current = false;
    }
  };

  useEffect(() => {
    void markRead();
    const onFocus = () => void markRead();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [messages, selected?.company, selected?.room, messageSearch]);

  const loadOlder = async () => {
    if (!selected || !messages.length || loadingOlder) return;
    const target = selected;
    const query = messageSearch;
    const filter = messageFilter;
    const activeThread = thread;
    const first = messages[0].seq;
    setLoadingOlder(true);
    try {
      const value = await request<Thread>('messages', {
        company: target.company,
        room: target.room,
        before: first,
        ...(query.trim() ? { q: query.trim() } : {}),
        ...(filter === 'all' ? {} : { [filter]: '1' }),
        ...(activeThread ? { thread: activeThread } : {}),
      });
      if (
        selectedRef.current?.company !== target.company ||
        selectedRef.current?.room !== target.room ||
        searchRef.current !== query ||
        filterRef.current !== filter ||
        threadRef.current !== activeThread
      ) {
        return;
      }
      const el = messageList.current;
      if (el) scrollRestore.current = { height: el.scrollHeight, top: el.scrollTop };
      historyLoaded.current = true;
      setHasMore(value.has_more);
      setMessages((current) => {
        const ids = new Set(current.map((m) => m.id));
        return [...value.items.filter((m) => !ids.has(m.id)), ...current];
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingOlder(false);
    }
  };

  useEffect(() => {
    setMentionPeople(null);
    setEmojiOpen(false);
    setShowMembers(false);
  }, [selected?.company, selected?.room]);

  const attach = async (list: FileList | null) => {
    if (!selected || !persisted.ready || !list?.length) return;
    persisted.markEdited(roomKey);
    const selectedFiles = Array.from(list);
    const extensions = /\.(png|jpe?g|pdf|xlsx|xls|csv|txt|docx|zip)$/i;
    if (
      selectedFiles.some((f) => !extensions.test(f.name)) ||
      files.length + selectedFiles.length > 5 ||
      files.reduce((n, f) => n + f.size, 0) + selectedFiles.reduce((n, f) => n + f.size, 0) > 12 * 1024 * 1024
    ) {
      setError('حداکثر پنج فایل مجاز (png, jpg, pdf, xlsx, docx, zip) با مجموع حجم ۱۲ مگابایت انتخاب کنید.');
      return;
    }
    const target = roomKey;
    try {
      const added = await Promise.all(
        selectedFiles.map(
          (f) =>
            new Promise<Attachment>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve({ name: f.name, data: String(reader.result).split(',')[1], size: f.size });
              reader.onerror = () => reject(Error('فایل خوانده نشد.'));
              reader.readAsDataURL(f);
            })
        )
      );
      setRoomFiles((current) => ({ ...current, [target]: [...(current[target] || []), ...added] }));
    } catch (e) {
      setError(String(e));
    }
  };

  const fetchFileBlobUrl = async (file: { id: string; name: string; mime?: string }) => {
    const value = await request<{ data: string }>('file', { id: file.id });
    const raw = atob(value.data);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const mime =
      file.mime ||
      (file.name.toLowerCase().endsWith('.png')
        ? 'image/png'
        : file.name.toLowerCase().endsWith('.webp')
          ? 'image/webp'
          : isImageName(file.name)
            ? 'image/jpeg'
            : 'application/octet-stream');
    return URL.createObjectURL(new Blob([bytes], { type: mime }));
  };

  const openOrDownload = async (file: { id: string; name: string; mime?: string }, previewOnly = false) => {
    try {
      const url = await fetchFileBlobUrl(file);
      if (previewOnly && isImageName(file.name)) {
        setImagePreview({ id: file.id, name: file.name, url });
        return;
      }
      const link = document.createElement('a');
      link.href = url;
      link.download = file.name.replace(/[\\/]/g, '_');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) {
      setError(String(e));
    }
  };

  const openScheduleModal = () => {
    if (!selected || (!draft.trim() && !files.length) || busy) return;
    if (reply) {
      setError('زمان‌بندی پاسخ به پیام پشتیبانی نمی‌شود؛ ابتدا پاسخ را لغو کنید.');
      return;
    }
    const now = new Date(Date.now() + 60 * 60 * 1000);
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    setScheduleModal({ date: todayJalali, time: `${hh}:${mm}` });
  };

  const submitSchedule = async () => {
    if (!selected || !scheduleModal || (!draft.trim() && !files.length) || busy) return;
    const target = selected;
    const text = draft;
    const targetKey = roomKey;
    const attachments = files.map(({ name, data }) => ({ name, data }));
    setBusy(true);
    try {
      const { iso } = await request<{ iso: string }>('parse_jalali', {
        date: scheduleModal.date,
        time: scheduleModal.time,
        future: true,
      });
      const key = JSON.stringify([target.company, target.room, text, attachments, iso]);
      if (scheduleAttempt.current?.key !== key) {
        scheduleAttempt.current = { key, id: crypto.randomUUID().replaceAll('-', '') };
      }
      await request('schedule', {
        company: target.company,
        room: target.room,
        text,
        attachments,
        due_at: iso,
        request_id: scheduleAttempt.current.id,
      });
      scheduleAttempt.current = null;
      setScheduleModal(null);
      setDrafts((current) => ({ ...current, [targetKey]: current[targetKey] === text ? '' : current[targetKey] }));
      setRoomFiles((current) => ({ ...current, [targetKey]: (current[targetKey] || []).filter((f) => !files.includes(f)) }));
      setInfoToast('پیام برای زمان انتخاب‌شده زمان‌بندی شد.');
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const loadScheduled = async () => {
    if (!selected) return;
    try {
      setScheduled(await request<Scheduled[]>('scheduled', { company: selected.company, room: selected.room }));
    } catch (e) {
      setError(String(e));
    }
  };

  const cancelScheduled = async () => {
    if (!cancelSchedule || busy) return;
    setBusy(true);
    try {
      await request('schedule_cancel', { id: cancelSchedule.id, expected_due_at: cancelSchedule.due_at });
      setCancelSchedule(null);
      await loadScheduled();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const submitPoll = async () => {
    if (!selected || !pollModal || busy) return;
    const title = pollModal.title.trim();
    const options = pollModal.optionsText
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!title) {
      setError('پرسش نظرسنجی را وارد کنید.');
      return;
    }
    if (options.length < 2 || options.length > 10 || new Set(options).size !== options.length) {
      setError('بین ۲ تا ۱۰ گزینه غیرتکراری وارد کنید.');
      return;
    }
    const target = selected;
    setBusy(true);
    try {
      const value = { title, payload: { options } };
      const key = JSON.stringify([target.company, target.room, 'poll', value]);
      if (specialAttempt.current?.key !== key) {
        specialAttempt.current = { key, id: crypto.randomUUID() };
      }
      await request('send', {
        company: target.company,
        room: target.room,
        text: title,
        kind: 'poll',
        payload: value.payload,
        request_id: specialAttempt.current.id,
      });
      specialAttempt.current = null;
      setPollModal(null);
      await refreshMessages(target);
      void refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const submitMeeting = async () => {
    if (!selected || !meetingModal || busy) return;
    const title = meetingModal.title.trim();
    if (!title) {
      setError('موضوع جلسه را وارد کنید.');
      return;
    }
    const target = selected;
    setBusy(true);
    try {
      const { iso } = await request<{ iso: string }>('parse_jalali', {
        date: meetingModal.date,
        time: meetingModal.time,
        future: false,
      });
      const payload = { at: iso, location: meetingModal.location.trim() };
      const key = JSON.stringify([target.company, target.room, 'meeting', title, payload]);
      if (specialAttempt.current?.key !== key) {
        specialAttempt.current = { key, id: crypto.randomUUID() };
      }
      await request('send', {
        company: target.company,
        room: target.room,
        text: title,
        kind: 'meeting',
        payload,
        request_id: specialAttempt.current.id,
      });
      specialAttempt.current = null;
      setMeetingModal(null);
      await refreshMessages(target);
      void refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    if (!selected || (!draft.trim() && !files.length) || busy) return;
    setBusy(true);
    const text = draft;
    const target = selected;
    const targetKey = roomKey;
    const attachments = files.map(({ name, data }) => ({ name, data }));
    const key = JSON.stringify([target.company, target.room, text, attachments, reply?.id || thread]);
    if (pendingSend.current?.key !== key) {
      pendingSend.current = { key, id: crypto.randomUUID() };
    }
    const requestId = pendingSend.current.id;
    const version = persisted.nextVersion(targetKey);
    try {
      await request('queue_enqueue', {
        payload: {
          company: target.company,
          room: target.room,
          text,
          attachments,
          reply_to: reply?.id || thread || null,
          request_id: requestId,
        },
        draft_version: version,
      });
      pendingSend.current = null;
      setDrafts((current) => ({ ...current, [targetKey]: current[targetKey] === text ? '' : current[targetKey] }));
      setRoomFiles((current) => ({ ...current, [targetKey]: (current[targetKey] || []).filter((f) => !files.includes(f)) }));
      setReplyByRoom((current) => ({ ...current, [targetKey]: undefined }));
      await refreshQueue();
      void flushQueue();
    } catch (e) {
      setError('پیام در کادر باقی ماند: ' + String(e));
    } finally {
      setBusy(false);
    }
  };

  const createFromMessage = async (message: Message, kind: 'native_reminder' | 'native_task') => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await request(kind, { company: selected.company, room: selected.room, id: message.id });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const messageAction = async (message: Message, action: string, option?: number) => {
    if (!selected || busy) return;
    const target = selected;
    setBusy(true);
    try {
      await request('message_action', { id: message.id, action, ...(option === undefined ? {} : { option }) });
      await refreshMessages(target, message.seq + 1);
      setConfirmDelete(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const forward = async (target: Room) => {
    if (!forwarding || busy) return;
    const msg = forwarding;
    setBusy(true);
    try {
      const attachments = await Promise.all(
        (msg.files || []).map(async (file) => ({
          name: file.name,
          data: (await request<{ data: string }>('file', { id: file.id })).data,
        }))
      );
      let text = msg.text || 'پیام ارسالی';
      if (msg.kind === 'poll') text += '\n' + (msg.payload?.options || []).join('\n');
      if (msg.kind === 'meeting' && msg.payload?.at) text += '\n' + formatTehranDateTime(msg.payload.at);
      const key = JSON.stringify([msg.id, target.company, target.room, text, attachments]);
      if (forwardAttempt.current?.key !== key) {
        forwardAttempt.current = { key, id: crypto.randomUUID() };
      }
      await request('send', {
        company: target.company,
        room: target.room,
        text,
        attachments,
        request_id: forwardAttempt.current.id,
      });
      forwardAttempt.current = null;
      setForwarding(null);
      await refresh();
      if (selectedRef.current?.company === target.company && selectedRef.current?.room === target.room) {
        await refreshMessages(target);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const visibleRooms = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rooms.filter((r) => {
      const name = roomDisplayName(r);
      const hasDraft = Boolean((drafts[JSON.stringify([r.company, r.room])] || '').trim());
      if (q && !name.toLowerCase().includes(q) && !(r.last?.text || '').toLowerCase().includes(q)) return false;
      if (roomFilter === 'unread') return Boolean(r.unread && r.unread > 0);
      if (roomFilter === 'saved') return Boolean(r.saved);
      if (roomFilter === 'direct') return Boolean(r.direct);
      if (roomFilter === 'group') return !r.direct && !r.saved;
      if (roomFilter === 'drafts') return hasDraft;
      return true;
    });
  }, [rooms, search, roomFilter, drafts]);

  const filterLabels: Record<RoomFilter, string> = {
    all: 'همه گفتگوها',
    unread: 'خوانده‌نشده‌ها',
    saved: 'پیام‌های ذخیره‌شده',
    direct: 'گفتگوهای شخصی',
    group: 'گروه‌ها',
    drafts: 'دارای پیش‌نویس',
  };

  return (
    <main dir="rtl" className="glass-backdrop flex h-screen w-full overflow-hidden text-foreground select-text">
      {/* LTR PanelGroup ensures RTL visual placement (Sidebar on Right, Chat on Left) AND accurate mouse drag direction */}
      <ResizablePanelGroup dir="ltr" direction="horizontal" className="h-full w-full min-w-0">
        {/* Left pane in LTR = Main Chat Window */}
        <ResizablePanel defaultSize={73} minSize={45}>
          <section dir="rtl" className="flex h-full min-w-0 flex-col">
            {/* Chat Header (faithful to chat-template.tsx + liquid glass) */}
            <header className="glass-surface z-10 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4">
              <div className="flex min-w-0 items-center gap-3">
                {selected ? (
                  <>
                    <Avatar className="size-11 shrink-0 ring-2 ring-white/50 dark:ring-white/15">
                      <AvatarImage src={selected.avatar ? 'data:image/png;base64,' + selected.avatar : undefined} />
                      <AvatarFallback className="bg-primary/15 font-bold text-primary">
                        {selected.saved ? <Bookmark className="size-4" /> : roomDisplayName(selected)[0]}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {thread && (
                          <button
                            onClick={() => setThread('')}
                            className="rounded-lg bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary hover:bg-primary/20"
                          >
                            بازگشت به گفتگو
                          </button>
                        )}
                        <h2 className="truncate text-base font-bold text-foreground">
                          {thread ? `بحث گفتگو · ${roomDisplayName(selected)}` : roomDisplayName(selected)}
                        </h2>
                      </div>
                      <p className="truncate text-xs text-muted-foreground">
                        {selected.saved
                          ? 'فضای خصوصی پیام‌های ذخیره‌شده شما'
                          : selected.direct
                            ? 'گفتگوی شخصی دوطرفه'
                            : membersList.length
                              ? `${membersList.length.toLocaleString('fa-IR')} عضو${selected.company_name ? ' · ' + selected.company_name : ''}`
                              : selected.company_name || 'گفتگوی گروهی شرکت'}
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="text-sm font-medium text-muted-foreground">یک گفتگو را از فهرست انتخاب کنید</div>
                )}
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                {queue.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowQueue(true);
                      void refreshQueue();
                    }}
                    className="glass-pill gap-1.5 rounded-full border-amber-400/50 text-amber-700 dark:text-amber-300"
                  >
                    <RefreshCw className="size-3.5" />
                    <span>صف ارسال ({queue.length.toLocaleString('fa-IR')})</span>
                  </Button>
                )}

                {selected && (
                  <>
                    <Button
                      variant={showMessageSearch ? 'secondary' : 'ghost'}
                      size="icon"
                      title="جستجو و فیلتر در پیام‌ها"
                      aria-label="جستجو در پیام‌ها"
                      onClick={() => setShowMessageSearch((v) => !v)}
                      className="rounded-full"
                    >
                      <Search className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title={selected.muted ? 'فعال‌کردن اعلان' : 'بی‌صدا کردن گفتگو'}
                      aria-label={selected.muted ? 'فعال‌کردن اعلان' : 'بی‌صدا کردن گفتگو'}
                      disabled={busy}
                      onClick={() => void toggleMute()}
                      className="rounded-full"
                    >
                      {selected.muted ? <BellOff className="size-4 text-amber-500" /> : <Bell className="size-4" />}
                    </Button>
                    <DropdownMenu dir="rtl">
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="گزینه‌های گفتگو" className="rounded-full">
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="glass-modal min-w-52 rounded-2xl p-1.5">
                        <DropdownMenuItem onClick={() => setShowMembers(true)} className="cursor-pointer gap-2 rounded-xl">
                          <Users className="size-4" /> اعضای گفتگو
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void loadScheduled()} className="cursor-pointer gap-2 rounded-xl">
                          <Clock className="size-4" /> پیام‌های زمان‌بندی‌شده
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => {
                            setShowQueue(true);
                            void refreshQueue();
                          }}
                          className="cursor-pointer gap-2 rounded-xl"
                        >
                          <RefreshCw className="size-4" /> صف ارسال ({queue.length.toLocaleString('fa-IR')})
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => void startClearRoom()}
                          className="cursor-pointer gap-2 rounded-xl text-amber-600 dark:text-amber-400"
                        >
                          <Trash2 className="size-4" /> پاک‌کردن پیام‌ها برای همه
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setHideRoom(selected)}
                          className="cursor-pointer gap-2 rounded-xl text-red-600 dark:text-red-400"
                        >
                          <Archive className="size-4" /> حذف از فهرست / غیرفعال‌سازی
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}
              </div>
            </header>

            {/* Expandable Message Search & Filter Subbar */}
            {selected && showMessageSearch && (
              <div className="glass-subtle flex flex-wrap items-center gap-2 border-b border-border/50 px-4 py-2.5">
                <div className="relative min-w-48 flex-1">
                  <Search className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    aria-label="جستجو در پیام‌ها"
                    className="h-9 rounded-xl bg-background/70 pr-9 text-sm"
                    placeholder="جستجو در متن یا پیوست پیام‌ها…"
                    value={messageSearch}
                    onChange={(e) => setMessageSearch(e.target.value)}
                  />
                </div>
                <select
                  aria-label="فیلتر پیام‌ها"
                  value={messageFilter}
                  onChange={(e) => setMessageFilter(e.target.value as 'all' | 'saved' | 'pinned')}
                  className="h-9 rounded-xl border border-border/70 bg-background/80 px-3 text-sm text-foreground outline-none"
                >
                  <option value="all">همه پیام‌ها</option>
                  <option value="saved">ذخیره‌شده</option>
                  <option value="pinned">سنجاق‌شده</option>
                </select>
                {(messageSearch || messageFilter !== 'all') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setMessageSearch('');
                      setMessageFilter('all');
                    }}
                    className="rounded-xl text-xs"
                  >
                    پاک‌کردن فیلتر
                  </Button>
                )}
              </div>
            )}

            {/* Status / Error Notifications */}
            {(error || infoToast) && (
              <div className="space-y-1 px-4 pt-2">
                {error && (
                  <div
                    role="alert"
                    className="flex items-center justify-between gap-2 rounded-xl border border-red-500/35 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-700 dark:text-red-300"
                  >
                    <span>
                      {error}
                      {persisted.failed && (
                        <button onClick={persisted.retry} className="mr-3 font-bold underline">
                          تلاش دوباره
                        </button>
                      )}
                    </span>
                    <button aria-label="بستن خطا" onClick={() => setError('')} className="rounded p-0.5 hover:bg-red-500/15">
                      <X className="size-3.5" />
                    </button>
                  </div>
                )}
                {infoToast && (
                  <div className="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/35 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                    <span>{infoToast}</span>
                    <button onClick={() => setInfoToast('')} className="rounded p-0.5 hover:bg-emerald-500/15">
                      <X className="size-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Message Feed */}
            <div
              ref={messageList}
              onScroll={(e) => {
                const el = e.currentTarget;
                followLatest.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                if (followLatest.current) void markRead();
              }}
              className="flex flex-1 flex-col gap-3 overflow-y-auto px-5 py-4"
            >
              {!selected && (
                <div className="m-auto max-w-sm rounded-3xl p-8 text-center glass-card">
                  <MessageSquare className="mx-auto mb-3 size-10 text-primary opacity-80" />
                  <h3 className="mb-1 text-base font-bold">گفتگوهای کارنامه</h3>
                  <p className="text-xs leading-6 text-muted-foreground">
                    یک گفتگوی گروهی یا شخصی را انتخاب کنید، یا از بالای فهرست سمت راست یک گفتگوی جدید بسازید.
                  </p>
                </div>
              )}

              {selected && hasMore && (
                <button
                  disabled={loadingOlder}
                  onClick={() => void loadOlder()}
                  className="glass-pill self-center rounded-full px-4 py-1.5 text-xs font-medium text-foreground transition hover:bg-accent"
                >
                  {loadingOlder ? 'در حال دریافت…' : 'نمایش پیام‌های پیشین'}
                </button>
              )}

              {selected && !messages.length && (
                <div className="m-auto rounded-2xl px-6 py-4 text-center text-xs text-muted-foreground glass-subtle">
                  {messageSearch || messageFilter !== 'all' ? 'پیامی مطابق جستجو یا فیلتر پیدا نشد.' : 'هنوز پیامی در این گفتگو ثبت نشده است.'}
                </div>
              )}

              {messages.map((m) => {
                const isMine = Boolean(userId && m.author === userId);
                return (
                  <article
                    key={m.id}
                    className={`group relative flex max-w-[min(36rem,84%)] flex-col gap-1.5 rounded-2xl px-4 py-3 shadow-sm transition-all ${
                      isMine
                        ? 'self-start rounded-tr-sm border border-sky-400/40 bg-sky-500/14 dark:border-sky-400/30 dark:bg-sky-500/20'
                        : 'glass-card self-end rounded-tl-sm'
                    }`}
                  >
                    {/* Author row */}
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        {!isMine && (
                          <Avatar className="size-6">
                            <AvatarImage src={m.person?.avatar ? 'data:image/png;base64,' + m.person.avatar : undefined} />
                            <AvatarFallback className="bg-primary/15 text-[10px] font-bold text-primary">
                              {(m.person?.fullname || 'ک')[0]}
                            </AvatarFallback>
                          </Avatar>
                        )}
                        <span className="text-xs font-bold text-foreground/85">{isMine ? 'شما' : m.person?.fullname || 'کاربر'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {m.pinned && <Pin className="size-3 text-amber-500" aria-label="سنجاق‌شده" />}
                        {m.saved && <Bookmark className="size-3 text-sky-500" aria-label="ذخیره‌شده" />}
                      </div>
                    </div>

                    {/* Reply Excerpt */}
                    {m.reply_excerpt && (
                      <blockquote className="rounded-lg border-r-2 border-primary/70 bg-background/45 px-2.5 py-1 text-xs text-muted-foreground">
                        {m.reply_excerpt}
                      </blockquote>
                    )}

                    {/* Message Body */}
                    {m.text && <div className="whitespace-pre-wrap break-words py-0.5 text-sm leading-7 text-foreground">{m.text}</div>}

                    {/* Meeting Card */}
                    {!m.deleted && m.kind === 'meeting' && m.payload?.at && (
                      <div className="mt-1 flex flex-col gap-1 rounded-xl border border-indigo-400/35 bg-indigo-500/10 px-3 py-2 text-xs">
                        <div className="flex items-center gap-1.5 font-semibold text-indigo-700 dark:text-indigo-300">
                          <Calendar className="size-3.5" />
                          <span>{formatTehranDateTime(m.payload.at)}</span>
                        </div>
                        {m.payload.location && <div className="text-foreground/80">محل / پیوند: {m.payload.location}</div>}
                      </div>
                    )}

                    {/* Poll Card */}
                    {!m.deleted && m.kind === 'poll' && m.payload?.options && (
                      <div className="mt-1 flex flex-col gap-1.5">
                        {m.payload.options.map((option, i) => {
                          const totalVotes = (m.votes || []).reduce((a, b) => a + b, 0);
                          const count = m.votes?.[i] || 0;
                          const pct = totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0;
                          const voted = m.my_vote === i;
                          return (
                            <button
                              key={i}
                              disabled={busy}
                              onClick={() => void messageAction(m, 'vote', i)}
                              className={`relative overflow-hidden rounded-xl border px-3 py-2 text-right text-xs transition ${
                                voted
                                  ? 'border-emerald-500/60 bg-emerald-500/12 font-semibold text-foreground'
                                  : 'border-border/70 bg-background/55 hover:bg-accent/70'
                              }`}
                            >
                              <div
                                className="pointer-events-none absolute inset-y-0 right-0 bg-primary/12 transition-all"
                                style={{ width: `${pct}%` }}
                              />
                              <div className="relative flex items-center justify-between gap-2">
                                <span>
                                  {voted && '✓ '}
                                  {option}
                                </span>
                                <span className="text-[11px] text-muted-foreground">{count.toLocaleString('fa-IR')}</span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {/* File Attachments */}
                    {!m.deleted &&
                      m.files?.map((file) => (
                        <div
                          key={file.id}
                          className="mt-1 flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/55 px-2.5 py-1.5 text-xs"
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            {isImageName(file.name) ? (
                              <ImageIcon className="size-4 shrink-0 text-sky-500" />
                            ) : (
                              <FileText className="size-4 shrink-0 text-primary" />
                            )}
                            <span className="truncate font-medium">{file.name}</span>
                            {file.size ? <span className="shrink-0 text-[10px] text-muted-foreground">{formatBytes(file.size)}</span> : null}
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
                            {isImageName(file.name) && (
                              <button
                                onClick={() => void openOrDownload(file, true)}
                                className="rounded-lg px-2 py-1 text-[11px] font-medium text-sky-600 hover:bg-sky-500/15 dark:text-sky-300"
                              >
                                نمایش
                              </button>
                            )}
                            <button
                              onClick={() => void openOrDownload(file, false)}
                              title="ذخیره پیوست"
                              className="rounded-lg p-1 text-primary hover:bg-primary/15"
                            >
                              <Download className="size-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}

                    {/* Footer Meta & Context Actions */}
                    {!m.deleted && (
                      <div className="mt-1 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <time title={formatTehranDateTime(m.created)}>{formatTehranTime(m.created)}</time>
                          {isMine && (
                            <button
                              type="button"
                              onClick={() => setSeenModal(m)}
                              title={(m.seen_by || []).map((x) => x.fullname).join('، ') || 'هنوز دیده نشده'}
                              className="inline-flex items-center gap-0.5 rounded px-1 hover:bg-black/5 dark:hover:bg-white/10"
                            >
                              {m.seen_by?.length ? <CheckCheck className="size-3.5 text-sky-500" /> : <Check className="size-3.5" />}
                            </button>
                          )}
                          {!!m.likes?.length && (
                            <button
                              onClick={() => void messageAction(m, 'like')}
                              title={m.likes.map((x) => x.fullname).join('، ')}
                              className="inline-flex items-center gap-1 rounded-full bg-rose-500/12 px-1.5 py-0.5 text-[10px] text-rose-600 dark:text-rose-300"
                            >
                              <Heart className="size-3 fill-current" />
                              {m.likes.length.toLocaleString('fa-IR')}
                            </button>
                          )}
                          {!!m.reply_count && !thread && (
                            <button
                              onClick={() => setThread(m.thread_root || m.id)}
                              className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20"
                            >
                              {m.reply_count.toLocaleString('fa-IR')} پاسخ
                            </button>
                          )}
                        </div>

                        <DropdownMenu dir="rtl">
                          <DropdownMenuTrigger asChild>
                            <button
                              aria-label="گزینه‌های پیام"
                              className="rounded-full px-1.5 py-0.5 text-foreground/70 transition hover:bg-black/10 dark:hover:bg-white/10"
                            >
                              ⋯
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="start" className="glass-modal min-w-44 rounded-2xl p-1.5 text-xs">
                            <DropdownMenuItem
                              disabled={!persisted.ready}
                              onClick={() => {
                                persisted.markEdited(roomKey);
                                setReplyByRoom((current) => ({ ...current, [roomKey]: m }));
                                requestAnimationFrame(() => composeRef.current?.focus());
                              }}
                              className="cursor-pointer gap-2 rounded-xl"
                            >
                              <Reply className="size-3.5" /> پاسخ
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setThread(m.thread_root || m.id)} className="cursor-pointer gap-2 rounded-xl">
                              <MessageSquare className="size-3.5" /> بحث{' '}
                              {m.reply_count ? `(${m.reply_count.toLocaleString('fa-IR')})` : ''}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setForwarding(m)} className="cursor-pointer gap-2 rounded-xl">
                              <Forward className="size-3.5" /> ارسال به گفتگوی دیگر
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => void createFromMessage(m, 'native_task')}
                              className="cursor-pointer gap-2 rounded-xl"
                            >
                              <CheckSquare className="size-3.5" /> ساخت کار
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => void createFromMessage(m, 'native_reminder')}
                              className="cursor-pointer gap-2 rounded-xl"
                            >
                              <Calendar className="size-3.5" /> افزودن یادآور به تقویم
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => void messageAction(m, 'like')} className="cursor-pointer gap-2 rounded-xl">
                              <Heart className="size-3.5" /> پسند{' '}
                              {m.likes?.length ? `(${m.likes.length.toLocaleString('fa-IR')})` : ''}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => void messageAction(m, 'save')} className="cursor-pointer gap-2 rounded-xl">
                              <Bookmark className="size-3.5" /> {m.saved ? 'لغو ذخیره' : 'ذخیره پیام'}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => void messageAction(m, 'pin')} className="cursor-pointer gap-2 rounded-xl">
                              <Pin className="size-3.5" /> {m.pinned ? 'برداشتن سنجاق' : 'سنجاق پیام'}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setSeenModal(m)} className="cursor-pointer gap-2 rounded-xl">
                              <Eye className="size-3.5" /> وضعیت دیده‌شدن
                            </DropdownMenuItem>
                            {m.can_delete && (
                              <>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => setConfirmDelete(m)}
                                  className="cursor-pointer gap-2 rounded-xl text-red-600 dark:text-red-400"
                                >
                                  <Trash2 className="size-3.5" /> حذف برای همه
                                </DropdownMenuItem>
                              </>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            {/* Bottom Composer Bar (faithful to chat-template.tsx + liquid glass) */}
            <footer className="glass-surface shrink-0 border-t border-border/60 p-3">
              {reply && (
                <div className="mb-2 flex items-center justify-between gap-2 rounded-xl border-r-2 border-primary bg-background/60 px-3 py-1.5 text-xs">
                  <span className="truncate text-foreground/85">پاسخ به: {reply.text.slice(0, 90)}</span>
                  <button
                    aria-label="لغو پاسخ"
                    onClick={() => {
                      persisted.markEdited(roomKey);
                      setReplyByRoom((current) => ({ ...current, [roomKey]: undefined }));
                    }}
                    className="rounded p-0.5 hover:bg-black/10 dark:hover:bg-white/10"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              )}

              {files.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {files.map((f, i) => (
                    <button
                      key={i}
                      onClick={() =>
                        setRoomFiles((current) => ({ ...current, [roomKey]: (current[roomKey] || []).filter((_, j) => j !== i) }))
                      }
                      className="glass-pill inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs"
                    >
                      <Paperclip className="size-3" />
                      <span>{f.name}</span>
                      <X className="size-3 opacity-70" />
                    </button>
                  ))}
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                multiple
                hidden
                accept=".png,.jpg,.jpeg,.pdf,.xlsx,.xls,.csv,.txt,.docx,.zip"
                onChange={(e) => {
                  void attach(e.target.files);
                  e.target.value = '';
                }}
              />

              <div className="glass-card flex items-center gap-1.5 rounded-2xl px-2 py-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="انتخاب شکلک"
                  disabled={!selected || !persisted.ready}
                  onClick={() => setEmojiOpen(true)}
                  className="size-9 shrink-0 rounded-xl"
                >
                  <Smile className="size-5 text-muted-foreground" />
                </Button>

                <DropdownMenu dir="rtl">
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="ابزارهای ارسال و پیوست"
                      disabled={!selected}
                      className="size-9 shrink-0 rounded-xl"
                    >
                      <Paperclip className="size-5 text-muted-foreground" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="glass-modal min-w-48 rounded-2xl p-1.5 text-sm">
                    <DropdownMenuItem
                      disabled={!selected || !persisted.ready}
                      onClick={() => fileInputRef.current?.click()}
                      className="cursor-pointer gap-2 rounded-xl"
                    >
                      <ImageIcon className="size-4 text-sky-500" /> پیوست فایل یا تصویر
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      disabled={!selected || busy}
                      onClick={() => setPollModal({ title: '', optionsText: '' })}
                      className="cursor-pointer gap-2 rounded-xl"
                    >
                      <Vote className="size-4 text-emerald-500" /> نظرسنجی جدید
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      disabled={!selected || busy}
                      onClick={() => setMeetingModal({ title: '', date: todayJalali, time: '10:00', location: '' })}
                      className="cursor-pointer gap-2 rounded-xl"
                    >
                      <Calendar className="size-4 text-indigo-500" /> جلسه تازه
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      disabled={busy || !selected || (!draft.trim() && !files.length)}
                      onClick={openScheduleModal}
                      className="cursor-pointer gap-2 rounded-xl"
                    >
                      <Clock className="size-4 text-amber-500" /> ارسال زمان‌دار
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  title="اشاره به عضو (@)"
                  aria-label="اشاره به عضو"
                  disabled={!selected || !persisted.ready}
                  onClick={() => void chooseMention()}
                  className="size-9 shrink-0 rounded-xl"
                >
                  <AtSign className="size-4 text-muted-foreground" />
                </Button>

                <textarea
                  ref={composeRef}
                  rows={1}
                  className="max-h-32 min-h-[38px] min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder={selected ? 'پیام خود را بنویسید… (Enter ارسال، Shift+Enter خط بعد)' : 'ابتدا یک گفتگو را انتخاب کنید…'}
                  value={draft}
                  disabled={!selected || !persisted.ready}
                  onChange={(e) => {
                    persisted.markEdited(roomKey);
                    const value = e.target.value;
                    setDrafts((current) => ({ ...current, [roomKey]: value }));
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && !(e.nativeEvent as KeyboardEvent).isComposing) {
                      e.preventDefault();
                      if (!busy && selected && persisted.ready && (draft.trim() || files.length)) {
                        void send();
                      }
                    }
                  }}
                />

                <Button
                  type="button"
                  disabled={busy || !selected || !persisted.ready || (!draft.trim() && !files.length)}
                  onClick={() => void send()}
                  aria-label="ارسال"
                  className="h-9 shrink-0 gap-1.5 rounded-xl bg-primary px-4 text-primary-foreground shadow-sm transition hover:opacity-90 disabled:opacity-40"
                >
                  <Send className="size-4" />
                  <span className="text-xs font-semibold">ارسال</span>
                </Button>
              </div>
            </footer>
          </section>
        </ResizablePanel>

        <ResizableHandle className="bg-border/60 transition-colors hover:bg-primary/40" />

        {/* Right pane in LTR = Conversation Sidebar (RTL visual right side) */}
        <ResizablePanel defaultSize={27} minSize={20} maxSize={42}>
          <aside dir="rtl" className="glass-surface flex h-full min-w-0 flex-col border-l border-border/60">
            {/* Sidebar Header (chat-template.tsx fidelity) */}
            <header className="flex h-16 shrink-0 items-center justify-between px-4">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight">چت‌ها</h1>
                {roomFilter !== 'all' && (
                  <button
                    onClick={() => setRoomFilter('all')}
                    className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/25"
                  >
                    {filterLabels[roomFilter]} ×
                  </button>
                )}
              </div>
              <div className="flex items-center gap-1">
                <DropdownMenu dir="rtl">
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="شروع گفتگوی تازه" className="rounded-full">
                      <SquarePen className="size-5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="glass-modal min-w-48 rounded-2xl p-1.5 text-sm">
                    <DropdownMenuItem onClick={() => void startCreate('direct')} className="cursor-pointer gap-2 rounded-xl">
                      <SquarePen className="size-4" /> گفتگوی شخصی تازه
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => void startCreate('group')} className="cursor-pointer gap-2 rounded-xl">
                      <Users className="size-4" /> ساخت گروه جدید
                    </DropdownMenuItem>
                    {userId && !rooms.some((r) => r.room === 'saved:' + userId) && (
                      <DropdownMenuItem onClick={() => void openSaved()} className="cursor-pointer gap-2 rounded-xl">
                        <Bookmark className="size-4 text-sky-500" /> پیام‌های ذخیره‌شده من
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => setRestoreOpen(true)} className="cursor-pointer gap-2 rounded-xl">
                      <RotateCcw className="size-4" /> بازیابی گروه پیش‌فرض
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <DropdownMenu dir="rtl">
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="فیلتر فهرست گفتگوها" className="rounded-full">
                      <ListFilter className="size-5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="glass-modal min-w-44 rounded-2xl p-1.5 text-sm">
                    {(Object.keys(filterLabels) as RoomFilter[]).map((key) => (
                      <DropdownMenuItem
                        key={key}
                        onClick={() => setRoomFilter(key)}
                        className="cursor-pointer justify-between rounded-xl"
                      >
                        <span>{filterLabels[key]}</span>
                        {roomFilter === key && <Check className="size-3.5 text-primary" />}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </header>

            {/* Search Conversations */}
            <div className="px-3 pb-3">
              <div className="relative">
                <Search className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="جستجوی گفتگوها…"
                  className="h-9 rounded-xl border-border/60 bg-background/60 pr-9 text-sm"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>

            {/* Real Rooms List */}
            <ScrollArea className="flex-1 px-2 pb-2">
              <div className="flex flex-col gap-1">
                {visibleRooms.map((r) => {
                  const isActive = selected?.company === r.company && selected?.room === r.room;
                  const title = roomDisplayName(r);
                  const rDraft = (drafts[JSON.stringify([r.company, r.room])] || '').trim();
                  return (
                    <button
                      key={r.company + '|' + r.room}
                      onClick={() => {
                        setMessageSearch('');
                        setMessageFilter('all');
                        setThread('');
                        setSelected(r);
                      }}
                      className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-right transition-all ${
                        isActive ? 'glass-card border-primary/35 ring-1 ring-primary/25' : 'hover:bg-accent/60'
                      }`}
                    >
                      <Avatar className="size-11 shrink-0">
                        <AvatarImage src={r.avatar ? 'data:image/png;base64,' + r.avatar : undefined} />
                        <AvatarFallback className="bg-primary/12 text-sm font-bold text-primary">
                          {r.saved ? <Bookmark className="size-4" /> : title[0]}
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold text-foreground">{title}</span>
                          {r.muted && <BellOff className="size-3.5 shrink-0 text-muted-foreground" />}
                        </div>
                        <div className="mt-0.5 flex items-center justify-between gap-2">
                          <span className="truncate py-0.5 text-xs leading-5 text-muted-foreground">
                            {rDraft ? (
                              <span className="text-amber-600 dark:text-amber-400">پیش‌نویس: {rDraft}</span>
                            ) : (
                              r.last?.text || ''
                            )}
                          </span>
                          {!!r.unread && (
                            <span
                              aria-label={`${r.unread} پیام خوانده‌نشده`}
                              className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-[11px] font-bold text-primary-foreground"
                            >
                              {r.unread.toLocaleString('fa-IR')}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })}

                {!visibleRooms.length && (
                  <p className="px-4 py-8 text-center text-xs text-muted-foreground">
                    {rooms.length ? 'گفتگویی با این جستجو یا فیلتر یافت نشد.' : 'هنوز گفتگویی در دسترس نیست.'}
                  </p>
                )}
              </div>
            </ScrollArea>
          </aside>
        </ResizablePanel>
      </ResizablePanelGroup>

      {/* Modals (Glassmorphic, RTL, Accessible) */}
      {emojiOpen && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="انتخاب شکلک" className="glass-modal w-[min(26.5rem,92vw)] rounded-3xl p-5">
            <header className="mb-3 flex items-center justify-between">
              <strong className="text-sm font-bold">انتخاب شکلک</strong>
              <button aria-label="بستن" onClick={() => setEmojiOpen(false)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            <div className="grid grid-cols-8 gap-1.5">
              {EMOJIS.map((emoji) => (
                <button
                  key={emoji}
                  aria-label={emoji}
                  onClick={() => insertEmoji(emoji)}
                  className="emoji-glyph flex h-10 w-10 items-center justify-center rounded-xl text-xl transition hover:scale-110 hover:bg-accent cursor-pointer"
                >
                  {emoji}
                </button>
              ))}
            </div>
          </section>
        </div>
      )}

      {mentionPeople && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="اشاره به عضو" className="glass-modal max-h-[80vh] w-[min(24rem,90vw)] overflow-auto rounded-3xl p-5">
            <header className="mb-3 flex items-center justify-between">
              <strong className="text-sm font-bold">اشاره به عضو</strong>
              <button aria-label="بستن" onClick={() => setMentionPeople(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {mentionPeople.map((person) => (
              <button
                key={person.id}
                onClick={() => insertMention(person)}
                className="block w-full rounded-xl px-3 py-2.5 text-right text-sm hover:bg-accent"
              >
                <span className="font-medium">{person.fullname}</span>{' '}
                <span className="text-xs text-muted-foreground">@{person.username}</span>
              </button>
            ))}
            {!mentionPeople.length && <p className="py-4 text-center text-xs text-muted-foreground">عضو دیگری برای اشاره وجود ندارد.</p>}
          </section>
        </div>
      )}

      {pollModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="نظرسنجی جدید" className="glass-modal w-[min(28rem,90vw)] rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">ساخت نظرسنجی</strong>
              <button aria-label="بستن" onClick={() => setPollModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            <Input
              placeholder="پرسش نظرسنجی را بنویسید…"
              value={pollModal.title}
              onChange={(e) => setPollModal((m) => (m ? { ...m, title: e.target.value } : null))}
            />
            <textarea
              rows={4}
              className="w-full rounded-xl border border-border bg-background/70 p-3 text-sm outline-none"
              placeholder="هر گزینه در یک خط (۲ تا ۱۰ گزینه)"
              value={pollModal.optionsText}
              onChange={(e) => setPollModal((m) => (m ? { ...m, optionsText: e.target.value } : null))}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setPollModal(null)}>انصراف</Button>
              <Button disabled={busy} onClick={() => void submitPoll()}>ارسال نظرسنجی</Button>
            </div>
          </section>
        </div>
      )}

      {meetingModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="جلسه تازه" className="glass-modal w-[min(28rem,90vw)] rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">ثبت جلسه تازه</strong>
              <button aria-label="بستن" onClick={() => setMeetingModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            <Input
              placeholder="موضوع جلسه"
              value={meetingModal.title}
              onChange={(e) => setMeetingModal((m) => (m ? { ...m, title: e.target.value } : null))}
            />
            <div className="grid grid-cols-2 gap-2">
              <Input
                dir="ltr"
                placeholder="تاریخ شمسی (مثلاً ۱۴۰۵/۰۸/۰۵)"
                value={meetingModal.date}
                onChange={(e) => setMeetingModal((m) => (m ? { ...m, date: e.target.value } : null))}
              />
              <Input
                dir="ltr"
                placeholder="ساعت (HH:MM)"
                value={meetingModal.time}
                onChange={(e) => setMeetingModal((m) => (m ? { ...m, time: e.target.value } : null))}
              />
            </div>
            <Input
              placeholder="محل یا پیوند جلسه (اختیاری)"
              value={meetingModal.location}
              onChange={(e) => setMeetingModal((m) => (m ? { ...m, location: e.target.value } : null))}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setMeetingModal(null)}>انصراف</Button>
              <Button disabled={busy} onClick={() => void submitMeeting()}>ارسال دعوت جلسه</Button>
            </div>
          </section>
        </div>
      )}

      {scheduleModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="زمان‌بندی ارسال" className="glass-modal w-[min(26rem,90vw)] rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">زمان‌بندی ارسال پیام</strong>
              <button aria-label="بستن" onClick={() => setScheduleModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            <p className="text-xs text-muted-foreground">تاریخ شمسی و ساعت تهران را برای ارسال خودکار مشخص کنید.</p>
            <div className="grid grid-cols-2 gap-2">
              <Input
                dir="ltr"
                placeholder="1405/08/25"
                value={scheduleModal.date}
                onChange={(e) => setScheduleModal((s) => (s ? { ...s, date: e.target.value } : null))}
              />
              <Input
                dir="ltr"
                placeholder="14:30"
                value={scheduleModal.time}
                onChange={(e) => setScheduleModal((s) => (s ? { ...s, time: e.target.value } : null))}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setScheduleModal(null)}>انصراف</Button>
              <Button disabled={busy} onClick={() => void submitSchedule()}>تأیید زمان‌بندی</Button>
            </div>
          </section>
        </div>
      )}

      {scheduled && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="پیام‌های زمان‌بندی‌شده" className="glass-modal max-h-[80vh] w-[min(30rem,90vw)] overflow-auto rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">پیام‌های زمان‌بندی‌شده</strong>
              <button aria-label="بستن" onClick={() => setScheduled(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {scheduled.length === 0 && <p className="py-4 text-center text-xs text-muted-foreground">پیام زمان‌بندی‌شده‌ای وجود ندارد.</p>}
            {scheduled.map((item) => (
              <div key={item.id} className="rounded-2xl border border-border/60 bg-background/50 p-3 space-y-1.5">
                <div className="text-sm font-medium">{item.text || item.file_names.join('، ')}</div>
                <div className="text-xs text-muted-foreground">{formatTehranDateTime(item.due_at)}</div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-primary">
                    {item.status === 'pending' ? 'در انتظار' : item.status === 'sending' ? 'در حال ارسال' : 'ارسال ناموفق'}
                  </span>
                  {item.status !== 'sending' && (
                    <Button variant="outline" size="sm" onClick={() => setCancelSchedule(item)} className="h-7 rounded-xl text-xs">
                      لغو ارسال
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </section>
        </div>
      )}

      {cancelSchedule && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(24rem,90vw)] rounded-3xl p-5 space-y-4">
            <p className="text-sm">ارسال این پیام زمان‌بندی‌شده لغو شود؟</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCancelSchedule(null)}>بازگشت</Button>
              <Button variant="destructive" disabled={busy} onClick={() => void cancelScheduled()}>لغو ارسال</Button>
            </div>
          </section>
        </div>
      )}

      {showQueue && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="صف ارسال" className="glass-modal max-h-[80vh] w-[min(30rem,90vw)] overflow-auto rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">صف ارسال (حفظ پیام تا تأیید مرکز)</strong>
              <button aria-label="بستن" onClick={() => setShowQueue(false)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {queue.length === 0 && <p className="py-4 text-center text-xs text-muted-foreground">صف ارسال خالی است.</p>}
            {queue.map((item) => (
              <div key={item.id} className="rounded-2xl border border-border/60 bg-background/50 p-3 space-y-2">
                <p className="text-sm font-medium">{item.text || 'پیام دارای پیوست'}</p>
                <p className="text-xs text-muted-foreground">{item.status === 'needs_review' ? 'نیازمند بررسی' : 'در انتظار ارسال'}</p>
                {item.error && <p className="text-xs text-red-600 dark:text-red-400">{item.error}</p>}
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => void queueAction(item, 'queue_retry')} className="h-8 rounded-xl text-xs">
                    تلاش دوباره
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setCancelQueued(item)} className="h-8 rounded-xl text-xs text-red-600">
                    حذف از صف
                  </Button>
                </div>
              </div>
            ))}
          </section>
        </div>
      )}

      {cancelQueued && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(24rem,90vw)] rounded-3xl p-5 space-y-4">
            <p className="text-sm">این پیام برای همیشه از صف ارسال حذف شود؟</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCancelQueued(null)}>بازگشت</Button>
              <Button variant="destructive" onClick={() => void queueAction(cancelQueued, 'queue_cancel')}>حذف از صف</Button>
            </div>
          </section>
        </div>
      )}

      {showMembers && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="اعضای گفتگو" className="glass-modal max-h-[80vh] w-[min(24rem,90vw)] overflow-auto rounded-3xl p-5 space-y-2">
            <header className="mb-2 flex items-center justify-between">
              <strong className="text-sm font-bold">اعضای گفتگو</strong>
              <button aria-label="بستن" onClick={() => setShowMembers(false)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {membersList.map((m) => (
              <div key={m.id} className="rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm">
                {m.fullname}
              </div>
            ))}
            {!membersList.length && <p className="py-4 text-center text-xs text-muted-foreground">عضوی برای نمایش وجود ندارد.</p>}
          </section>
        </div>
      )}

      {seenModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="وضعیت دیده‌شدن" className="glass-modal max-h-[75vh] w-[min(24rem,90vw)] overflow-auto rounded-3xl p-5 space-y-2">
            <header className="mb-2 flex items-center justify-between">
              <strong className="text-sm font-bold">دیده‌شده توسط</strong>
              <button aria-label="بستن" onClick={() => setSeenModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {seenModal.seen_by?.length ? (
              seenModal.seen_by.map((u, idx) => (
                <div key={idx} className="rounded-xl border border-border/50 bg-background/50 px-3 py-2 text-sm">
                  {u.fullname}
                </div>
              ))
            ) : (
              <p className="py-3 text-center text-xs text-muted-foreground">این پیام هنوز توسط سایر اعضا دیده نشده است.</p>
            )}
          </section>
        </div>
      )}

      {imagePreview && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 backdrop-blur-sm p-6">
          <section role="dialog" aria-modal="true" className="glass-modal flex max-h-[90vh] max-w-[90vw] flex-col gap-3 rounded-3xl p-4">
            <header className="flex items-center justify-between gap-4">
              <strong className="truncate text-sm">{imagePreview.name}</strong>
              <button
                aria-label="بستن پیش‌نمایش"
                onClick={() => {
                  URL.revokeObjectURL(imagePreview.url);
                  setImagePreview(null);
                }}
                className="rounded-lg p-1 hover:bg-accent"
              >
                <X className="size-4" />
              </button>
            </header>
            <img src={imagePreview.url} alt={imagePreview.name} className="max-h-[75vh] rounded-2xl object-contain" />
          </section>
        </div>
      )}

      {forwarding && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="ارسال به گفتگوی دیگر" className="glass-modal max-h-[80vh] w-[min(26rem,90vw)] overflow-auto rounded-3xl p-5 space-y-2">
            <header className="mb-2 flex items-center justify-between">
              <strong className="text-sm font-bold">ارسال به گفتگوی دیگر</strong>
              <button aria-label="بستن" onClick={() => setForwarding(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {rooms.map((room) => (
              <button
                key={room.company + '|' + room.room}
                disabled={busy}
                onClick={() => void forward(room)}
                className="block w-full rounded-xl px-3 py-2.5 text-right text-sm hover:bg-accent"
              >
                {roomDisplayName(room)}
              </button>
            ))}
          </section>
        </div>
      )}

      {clearConfirm && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/40 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(28rem,90vw)] rounded-3xl p-5 space-y-4">
            <h3 className="text-sm font-bold">پاک‌کردن پیام‌ها برای همه</h3>
            <p className="text-xs leading-6 text-muted-foreground">
              متن و پیوست‌های {clearConfirm.count.toLocaleString('fa-IR')} پیام فعلی برای همه اعضای این گفتگو در برنامه غیرقابل دسترس می‌شود. ادامه می‌دهید؟
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setClearConfirm(null)}>انصراف</Button>
              <Button variant="destructive" disabled={busy} onClick={() => void confirmClearRoom()}>پاک‌کردن پیام‌ها</Button>
            </div>
          </section>
        </div>
      )}

      {hideRoom && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/40 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(28rem,90vw)] rounded-3xl p-5 space-y-4">
            <h3 className="text-sm font-bold">تأیید گفتگو</h3>
            <p className="text-xs leading-6 text-muted-foreground">
              {hideRoom.saved
                ? 'پیام‌های ذخیره‌شده از فهرست شما پنهان می‌شوند و با ساخت دوباره در دسترس خواهند بود.'
                : hideRoom.direct
                  ? 'این گفتگوی شخصی فقط از فهرست شما پنهان می‌شود؛ پیام‌ها برای طرف مقابل باقی می‌مانند.'
                  : 'این گروه برای همه اعضای شرکت غیرفعال می‌شود؛ پیام‌ها حذف نمی‌شوند و مدیر می‌تواند گروه را بازگرداند.'}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setHideRoom(null)}>انصراف</Button>
              <Button variant="destructive" disabled={busy} onClick={() => void confirmHide()}>تأیید</Button>
            </div>
          </section>
        </div>
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/40 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(24rem,90vw)] rounded-3xl p-5 space-y-4">
            <p className="text-sm font-medium">این پیام برای همه اعضای گفتگو حذف شود؟</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirmDelete(null)}>انصراف</Button>
              <Button variant="destructive" disabled={busy} onClick={() => void messageAction(confirmDelete, 'delete')}>حذف پیام</Button>
            </div>
          </section>
        </div>
      )}

      {restoreOpen && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="بازیابی گروه" className="glass-modal w-[min(24rem,90vw)] rounded-3xl p-5 space-y-2">
            <header className="mb-2 flex items-center justify-between">
              <strong className="text-sm font-bold">بازیابی گروه پیش‌فرض</strong>
              <button aria-label="بستن" onClick={() => setRestoreOpen(false)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {[
              ['managers', 'گروه مدیران'],
              ['staff', 'گروه کارکنان'],
              ['general', 'گروه مشترک'],
            ].map(([id, label]) => (
              <button
                key={id}
                disabled={busy}
                onClick={() => void restoreDefaultGroup(id)}
                className="block w-full rounded-xl border border-border/50 bg-background/50 px-3 py-2.5 text-right text-sm hover:bg-accent"
              >
                {label}
              </button>
            ))}
          </section>
        </div>
      )}

      {createMode && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section
            role="dialog"
            aria-modal="true"
            aria-label={createMode === 'direct' ? 'گفتگوی شخصی' : 'گروه جدید'}
            className="glass-modal flex max-h-[82vh] w-[min(28rem,90vw)] flex-col gap-3 rounded-3xl p-5"
          >
            <header className="flex items-center justify-between font-bold">
              <span className="text-sm">{createMode === 'direct' ? 'شروع گفتگوی شخصی' : 'ساخت گروه جدید'}</span>
              <button aria-label="بستن" onClick={() => setCreateMode(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {createMode === 'group' && (
              <>
                <Input placeholder="نام گروه" maxLength={100} value={groupName} onChange={(e) => setGroupName(e.target.value)} />
                <select
                  aria-label="شرکت مرتبط"
                  className="h-9 rounded-xl border border-border bg-background/80 px-3 text-sm"
                  value={groupCompany}
                  onChange={(e) => setGroupCompany(e.target.value)}
                >
                  <option value="">بدون شرکت مرتبط</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                  <span>انتخاب عکس گروه:</span>
                  <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => chooseAvatar(e.target.files?.[0])} />
                </label>
                {groupAvatar && <img alt="پیش‌نمایش عکس گروه" src={'data:image/png;base64,' + groupAvatar} className="size-12 rounded-full object-cover" />}
              </>
            )}
            <div className="flex-1 overflow-auto rounded-2xl border border-border/50 bg-background/40 p-1">
              {people.map((person) =>
                createMode === 'direct' ? (
                  <button
                    key={person.id}
                    className="block w-full rounded-xl px-3 py-2 text-right text-sm hover:bg-accent"
                    disabled={busy}
                    onClick={() => void openDirect(person.id)}
                  >
                    {person.fullname}
                  </button>
                ) : (
                  <label key={person.id} className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-accent/60">
                    <input
                      type="checkbox"
                      checked={members.includes(person.id)}
                      onChange={(e) =>
                        setMembers(e.target.checked ? [...members, person.id] : members.filter((x) => x !== person.id))
                      }
                    />
                    {person.fullname}
                  </label>
                )
              )}
            </div>
            {createMode === 'group' && (
              <Button disabled={!groupName.trim() || busy} onClick={() => void createGroup()} className="rounded-xl">
                ساخت گروه
              </Button>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
