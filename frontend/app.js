const state = {
  credentials: null,
  user: null,
  menu: [],
  cart: new Map(),
  orders: [],
  chatSessionId: null,
  chatSessions: [],
  pendingOrderAttempt: (() => {
    try { return JSON.parse(sessionStorage.getItem("pending-order-attempt") || "null"); }
    catch { return null; }
  })(),
  cancelKeys: new Map(),
};

const byId = (id) => document.getElementById(id);
const money = (value) => `₹${Number(value).toFixed(2)}`;
const FOOD_IMAGES = {
  "South Indian": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=720&q=80",
  Rice: "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=720&q=80",
  Dessert: "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=720&q=80",
  "Main Course": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?auto=format&fit=crop&w=720&q=80",
  "North Indian": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=720&q=80",
  Starters: "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?auto=format&fit=crop&w=720&q=80",
};

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (state.credentials) headers.set("Authorization", state.credentials);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || `Request failed (${response.status})`);
  return payload;
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("visible"), 2800);
}

function setError(id, message = "") {
  byId(id).textContent = message;
}

function setSignedIn(user) {
  state.user = user;
  byId("account-status").textContent = `${user.full_name} · ${user.role.toLowerCase()}`;
  byId("login-toggle").classList.add("hidden");
  byId("logout-button").classList.remove("hidden");
  byId("login-panel").classList.add("hidden");
  byId("place-order").textContent = "Place order";
  byId("place-order").disabled = state.cart.size === 0;
  byId("admin-section").classList.toggle("hidden", user.role !== "ADMIN");
  loadOrders();
  byId("chat-input").disabled = false;
  byId("send-chat").disabled = false;
  loadChatSessions();
  if (user.role === "ADMIN") {
    loadAdminItems();
    loadAdminOrders();
  }
}

function clearSignedIn() {
  state.credentials = null;
  state.user = null;
  state.orders = [];
  byId("account-status").textContent = "Browsing as guest";
  byId("login-toggle").classList.remove("hidden");
  byId("logout-button").classList.add("hidden");
  byId("login-panel").classList.add("hidden");
  byId("admin-section").classList.add("hidden");
  state.chatSessionId = null;
  state.chatSessions = [];
  byId("chat-input").disabled = true;
  byId("send-chat").disabled = true;
  byId("chat-session-list").replaceChildren(makeText("p", "Sign in to save a conversation.", "muted"));
  byId("chat-transcript").replaceChildren(makeText("p", "Sign in to start a conversation with the restaurant assistant.", "muted"));
  byId("orders-list").replaceChildren(makeText("p", "Sign in to view your orders.", "muted"));
  byId("place-order").textContent = "Sign in to order";
  byId("place-order").disabled = true;
}

function makeText(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function renderMenu(items) {
  state.menu = items;
  const grid = byId("menu-grid");
  grid.replaceChildren();
  byId("menu-count").textContent = items.length ? `· ${items.length} dishes` : "· none found";
  const categories = [...new Set(items.map((item) => item.category))].sort();
  const categorySelect = byId("category-filter");
  const previous = categorySelect.value;
  categorySelect.replaceChildren(new Option("All categories", ""));
  categories.forEach((category) => categorySelect.add(new Option(category, category)));
  if (categories.includes(previous)) categorySelect.value = previous;
  if (items.length === 0) {
    grid.append(makeText("p", "No dishes match those filters.", "muted"));
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "menu-card";
    const top = document.createElement("div");
    top.className = "card-topline";
    top.append(makeText("span", item.category, "category-tag"));
    if (item.is_vegetarian) top.append(makeText("span", "VEGETARIAN", "diet-tag"));
    const title = makeText("h3", item.title);
    const image = document.createElement("img");
    image.className = "food-image";
    image.src = FOOD_IMAGES[item.category] || FOOD_IMAGES["Main Course"];
    image.alt = `${item.title}, illustrative food photograph`;
    image.loading = "lazy";
    image.addEventListener("error", () => image.remove(), { once: true });
    const description = makeText("p", item.description || "Prepared fresh by our fictional kitchen.", "description");
    const allergens = item.declared_allergens.length
      ? `Declared allergens: ${item.declared_allergens.join(", ")}. Cross-contact cannot be ruled out.`
      : "No declared allergens. Cross-contact cannot be ruled out.";
    const allergenNote = makeText("p", allergens, "allergen-note");
    const bottom = document.createElement("div");
    bottom.className = "card-bottom";
    const priceBlock = document.createElement("div");
    priceBlock.append(makeText("div", money(item.price), "price"));
    priceBlock.append(makeText("div", `${item.capacity} portions available`, "stock"));
    const addButton = makeText("button", "Add", "add-button");
    addButton.type = "button";
    addButton.disabled = item.capacity < 1;
    addButton.setAttribute("aria-label", `Add ${item.title} to basket`);
    addButton.addEventListener("click", () => addToCart(item));
    bottom.append(priceBlock, addButton);
    card.append(top, image, title, description, allergenNote, bottom);
    grid.append(card);
  });
}

async function loadMenu() {
  setError("menu-error");
  const params = new URLSearchParams();
  const keyword = byId("keyword-filter").value.trim();
  const category = byId("category-filter").value;
  const maximum = byId("price-filter").value;
  if (keyword) params.set("keyword", keyword);
  if (category) params.set("category", category);
  if (maximum) params.set("max_price", maximum);
  if (byId("vegetarian-filter").checked) params.set("vegetarian", "true");
  try {
    const items = await api(`/api/menu_items?${params.toString()}`);
    renderMenu(items);
  } catch (error) {
    setError("menu-error", error.message);
  }
}

function addToCart(item) {
  const current = state.cart.get(item.id)?.quantity || 0;
  if (current >= Math.min(10, item.capacity)) return showToast("That is the available portion limit.");
  state.cart.set(item.id, { item, quantity: current + 1 });
  state.pendingOrderAttempt = null;
  sessionStorage.removeItem("pending-order-attempt");
  renderCart();
  showToast(`${item.title} added to your basket.`);
}

function updateCart(itemId, difference) {
  const entry = state.cart.get(itemId);
  if (!entry) return;
  const quantity = entry.quantity + difference;
  if (quantity <= 0) state.cart.delete(itemId);
  else if (quantity <= Math.min(10, entry.item.capacity)) state.cart.set(itemId, { ...entry, quantity });
  state.pendingOrderAttempt = null;
  sessionStorage.removeItem("pending-order-attempt");
  renderCart();
}

function renderCart() {
  const container = byId("cart-lines");
  container.replaceChildren();
  let count = 0;
  let total = 0;
  if (state.cart.size === 0) container.append(makeText("p", "Choose something from the menu.", "muted"));
  state.cart.forEach(({ item, quantity }) => {
    count += quantity;
    total += Number(item.price) * quantity;
    const line = document.createElement("div");
    line.className = "cart-line";
    const details = document.createElement("div");
    details.append(makeText("strong", item.title));
    details.append(makeText("small", `${quantity} × ${money(item.price)}`));
    const controls = document.createElement("div");
    controls.className = "quantity-controls";
    const minus = makeText("button", "−");
    minus.type = "button";
    minus.setAttribute("aria-label", `Remove one ${item.title}`);
    minus.addEventListener("click", () => updateCart(item.id, -1));
    const number = makeText("span", String(quantity));
    const plus = makeText("button", "+");
    plus.type = "button";
    plus.setAttribute("aria-label", `Add one ${item.title}`);
    plus.addEventListener("click", () => updateCart(item.id, 1));
    controls.append(minus, number, plus);
    line.append(details, controls);
    container.append(line);
  });
  byId("cart-count").textContent = String(count);
  byId("cart-total").textContent = money(total);
  byId("place-order").disabled = !state.user || count === 0;
  if (state.user) byId("place-order").textContent = "Place order";
}

async function placeOrder() {
  if (!state.user) {
    byId("login-panel").classList.remove("hidden");
    byId("email-input").focus();
    return;
  }
  const items = [...state.cart.entries()].map(([menu_item_id, entry]) => ({ menu_item_id, quantity: entry.quantity })).sort((a, b) => a.menu_item_id - b.menu_item_id);
  const fingerprint = JSON.stringify(items);
  if (!state.pendingOrderAttempt || state.pendingOrderAttempt.fingerprint !== fingerprint) {
    state.pendingOrderAttempt = { fingerprint, key: crypto.randomUUID() };
    sessionStorage.setItem("pending-order-attempt", JSON.stringify(state.pendingOrderAttempt));
  }
  byId("place-order").disabled = true;
  setError("order-error");
  try {
    const order = await api("/api/orders", {
      method: "POST",
      headers: { "Idempotency-Key": state.pendingOrderAttempt.key },
      body: JSON.stringify({ items }),
    });
    state.cart.clear();
    state.pendingOrderAttempt = null;
    sessionStorage.removeItem("pending-order-attempt");
    renderCart();
    await Promise.all([loadMenu(), loadOrders()]);
    showToast(`Order #${order.id} placed · ${money(order.total_amount)}`);
  } catch (error) {
    setError("order-error", `${error.message} Retry keeps the same request key.`);
    byId("place-order").disabled = false;
  }
}

function renderOrders(orders) {
  state.orders = orders;
  const list = byId("orders-list");
  list.replaceChildren();
  if (orders.length === 0) list.append(makeText("p", "No orders yet.", "muted"));
  orders.forEach((order) => {
    const ticket = document.createElement("article");
    ticket.className = "order-ticket";
    const top = document.createElement("div");
    top.className = "ticket-top";
    top.append(makeText("span", `ORDER #${order.id}`, "ticket-number"));
    top.append(makeText("span", order.status, "status-pill"));
    const summary = order.lines.map((line) => `${line.quantity} × ${line.item_title_snapshot}`).join(" · ");
    ticket.append(top, makeText("p", `${summary} · ${money(order.total_amount)}`));
    if (["PLACED", "ACCEPTED"].includes(order.status)) {
      const cancel = makeText("button", "Cancel order", "cancel-button");
      cancel.type = "button";
      cancel.addEventListener("click", () => cancelOrder(order.id));
      ticket.append(cancel);
    }
    list.append(ticket);
  });
}

async function loadOrders() {
  if (!state.user) return;
  try {
    renderOrders(await api("/api/orders"));
  } catch (error) {
    byId("orders-list").replaceChildren(makeText("p", error.message, "muted"));
  }
}

async function cancelOrder(orderId) {
  if (!state.cancelKeys.has(orderId)) state.cancelKeys.set(orderId, crypto.randomUUID());
  try {
    await api(`/api/orders/${orderId}/cancel`, { method: "POST", headers: { "Idempotency-Key": state.cancelKeys.get(orderId) } });
    state.cancelKeys.delete(orderId);
    await Promise.all([loadOrders(), loadMenu()]);
    showToast("Cancellation confirmed by the order service.");
  } catch (error) {
    showToast(error.message);
  }
}

async function loadAdminItems() {
  try {
    const items = await api("/api/menu_items");
    const list = byId("admin-menu-list");
    list.replaceChildren();
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "admin-menu-row";
      const info = document.createElement("div");
      info.append(makeText("strong", item.title));
      info.append(makeText("small", `${money(item.price)} · ${item.capacity} portions`));
      const actions = document.createElement("div");
      actions.className = "admin-actions";
      const edit = makeText("button", "Edit");
      edit.type = "button";
      edit.addEventListener("click", () => editMenuItem(item));
      const disable = makeText("button", "Disable");
      disable.type = "button";
      disable.addEventListener("click", () => disableMenuItem(item.id));
      actions.append(edit, disable);
      row.append(info, actions);
      list.append(row);
    });
  } catch (error) {
    setError("admin-error", error.message);
  }
}

function editMenuItem(item) {
  byId("edit-item-id").value = String(item.id);
  byId("item-title").value = item.title;
  byId("item-category").value = item.category;
  byId("item-description").value = item.description;
  byId("item-price").value = item.price;
  byId("item-capacity").value = String(item.capacity);
  byId("item-vegetarian").checked = item.is_vegetarian;
  byId("item-allergens").value = item.declared_allergens.join(", ");
  byId("menu-editor-title").textContent = `Edit ${item.title}`;
  byId("menu-editor").scrollIntoView({ behavior: "smooth", block: "center" });
}

function resetEditor() {
  byId("menu-editor").reset();
  byId("edit-item-id").value = "";
  byId("menu-editor-title").textContent = "Add menu item";
}

async function saveMenuItem(event) {
  event.preventDefault();
  const id = byId("edit-item-id").value;
  const data = {
    title: byId("item-title").value.trim(),
    category: byId("item-category").value.trim(),
    description: byId("item-description").value.trim(),
    price: byId("item-price").value,
    capacity: Number(byId("item-capacity").value),
    is_vegetarian: byId("item-vegetarian").checked,
    declared_allergens: byId("item-allergens").value.split(",").map((value) => value.trim()).filter(Boolean),
  };
  try {
    await api(id ? `/api/menu_items/${id}` : "/api/menu_items", { method: id ? "PUT" : "POST", body: JSON.stringify(data) });
    resetEditor();
    await Promise.all([loadMenu(), loadAdminItems()]);
    showToast("Catalog saved.");
  } catch (error) {
    setError("admin-error", error.message);
  }
}

async function disableMenuItem(itemId) {
  try {
    await api(`/api/menu_items/${itemId}`, { method: "DELETE" });
    await Promise.all([loadMenu(), loadAdminItems()]);
    showToast("Catalog item disabled.");
  } catch (error) {
    setError("admin-error", error.message);
  }
}

async function uploadPolicyDocument(event) {
  event.preventDefault();
  const file = byId("policy-file").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("upload", file);
  setError("document-error");
  try {
    const document = await api("/api/documents", { method: "POST", body: form });
    byId("document-upload").reset();
    showToast(`${document.filename} indexed as version ${document.version}.`);
  } catch (error) {
    setError("document-error", error.message);
  }
}

function renderAdminOrderOptions(orders) {
  const select = byId("admin-order-select");
  const previous = select.value;
  select.replaceChildren(new Option("Choose an order", ""));
  orders.forEach((order) => select.add(new Option(`#${order.id} · ${order.status}`, String(order.id))));
  if (orders.some((order) => String(order.id) === previous)) select.value = previous;
}

async function loadAdminOrders() {
  try {
    renderAdminOrderOptions(await api("/api/admin/orders"));
  } catch (error) {
    setError("status-error", error.message);
  }
}

async function updateOrderStatus() {
  const orderId = byId("admin-order-select").value;
  if (!orderId) return setError("status-error", "Choose an order first.");
  try {
    await api(`/api/admin/orders/${orderId}/status`, { method: "PATCH", body: JSON.stringify({ status: byId("admin-status-select").value }) });
    setError("status-error");
    await loadOrders();
    await loadAdminOrders();
    showToast("Order status updated.");
  } catch (error) {
    setError("status-error", error.message);
  }
}

async function loadChatSessions() {
  if (!state.user) return;
  try {
    state.chatSessions = await api("/api/chat/sessions");
    const list = byId("chat-session-list");
    list.replaceChildren();
    if (state.chatSessions.length === 0) {
      list.append(makeText("p", "No saved conversations.", "muted"));
      await createChatSession();
      return;
    }
    state.chatSessions.forEach((session) => {
      const button = makeText("button", session.title, "chat-session-button");
      button.type = "button";
      button.setAttribute("aria-current", String(session.id === state.chatSessionId));
      button.addEventListener("click", () => openChatSession(session.id));
      list.append(button);
    });
    if (!state.chatSessions.some((session) => session.id === state.chatSessionId)) {
      await openChatSession(state.chatSessions[0].id);
    }
  } catch (error) {
    setError("chat-error", error.message);
  }
}

async function createChatSession() {
  if (!state.user) return;
  try {
    const session = await api("/api/chat/sessions", { method: "POST", body: JSON.stringify({ title: "New conversation" }) });
    state.chatSessionId = session.id;
    await loadChatSessions();
    await openChatSession(session.id);
  } catch (error) {
    setError("chat-error", error.message);
  }
}

async function openChatSession(sessionId) {
  state.chatSessionId = sessionId;
  setError("chat-error");
  try {
    const [messages, actions] = await Promise.all([
      api(`/api/chat/sessions/${sessionId}/messages`),
      api(`/api/chat/sessions/${sessionId}/actions`),
    ]);
    renderChatHistory(messages, actions);
    const list = byId("chat-session-list");
    list.querySelectorAll("button").forEach((button, index) => {
      button.setAttribute("aria-current", String(state.chatSessions[index]?.id === sessionId));
    });
  } catch (error) {
    setError("chat-error", error.message);
  }
}

function renderChatHistory(messages, actions = []) {
  const transcript = byId("chat-transcript");
  transcript.replaceChildren();
  if (messages.length === 0) transcript.append(makeText("p", "Ask about the menu, your orders, or a restaurant policy.", "muted"));
  messages.forEach((message) => appendChatMessage(message));
  actions.forEach((action) => appendPendingAction(action));
  transcript.scrollTop = transcript.scrollHeight;
}

function appendChatMessage(message) {
  const transcript = byId("chat-transcript");
  const bubble = document.createElement("article");
  bubble.className = `chat-message ${message.role === "USER" ? "user" : "assistant"}`;
  bubble.append(makeText("p", message.role === "USER" ? "You" : "Assistant", "chat-message-label"));
  bubble.append(makeText("p", message.content));
  if (message.citations?.length) {
    const sources = document.createElement("div");
    sources.className = "source-list";
    message.citations.forEach((citation) => {
      sources.append(makeText("span", `${citation.filename} · ${citation.section}`, "source-chip"));
    });
    bubble.append(sources);
  }
  transcript.append(bubble);
}

function appendPendingAction(action) {
  const transcript = byId("chat-transcript");
  const card = document.createElement("article");
  card.className = "pending-action";
  card.dataset.actionId = String(action.id);
  const heading = action.action_type === "CREATE_ORDER" ? "Order confirmation" : "Cancellation confirmation";
  card.append(makeText("h3", heading));
  const impact = action.impact || {};
  const details = action.action_type === "CREATE_ORDER"
    ? `${(impact.items || []).map((item) => `${item.quantity} × ${item.title} at ${money(item.unit_price)}`).join("\n")}\nTotal ${money(impact.total_amount)}`
    : `Order #${impact.order_id} · ${impact.current_status}\n${(impact.portions_returned || []).map((item) => `${item.quantity} × ${item.title} returned`).join("\n")}`;
  card.append(makeText("p", details));
  const buttons = document.createElement("div");
  buttons.className = "pending-buttons";
  if (action.status === "PENDING" || action.status === "PROCESSING") {
    const confirm = makeText("button", "Confirm", "button button-primary");
    confirm.type = "button";
    confirm.textContent = action.status === "PROCESSING" ? "Reconcile" : "Confirm";
    confirm.addEventListener("click", () => decideAction(action, "confirm", card, confirm));
    buttons.append(confirm);
    if (action.status === "PENDING") {
      const reject = makeText("button", "Reject", "button button-quiet");
      reject.type = "button";
      reject.addEventListener("click", () => decideAction(action, "reject", card, reject));
      buttons.append(reject);
    }
  } else {
    buttons.append(makeText("span", "Confirmation is processing. Refresh to reconcile.", "muted"));
  }
  card.append(buttons);
  transcript.append(card);
}

async function decideAction(action, decision, card, button) {
  button.disabled = true;
  setError("chat-error");
  try {
    const result = await api(`/api/chat/actions/${action.id}/${decision}`, {
      method: "POST",
      headers: { "Idempotency-Key": action.confirmation_key },
    });
    card.replaceChildren(makeText("h3", result.status === "CONFIRMED" ? "Action confirmed" : "Action rejected"));
    if (result.outcome?.order_id) card.append(makeText("p", `Order #${result.outcome.order_id} · ${result.outcome.status}`));
    await Promise.all([loadMenu(), loadOrders(), openChatSession(state.chatSessionId)]);
    showToast(result.status === "CONFIRMED" ? "The business service confirmed the action." : "The proposal was rejected.");
  } catch (error) {
    button.disabled = false;
    setError("chat-error", error.message);
  }
}

async function sendChatMessage(event) {
  event.preventDefault();
  if (!state.user) {
    byId("login-panel").classList.remove("hidden");
    return;
  }
  const content = byId("chat-input").value.trim();
  if (!content) return;
  if (!state.chatSessionId) await createChatSession();
  const sendButton = byId("send-chat");
  sendButton.disabled = true;
  byId("chat-status").textContent = "Assistant is checking…";
  setError("chat-error");
  try {
    const turn = await api(`/api/chat/sessions/${state.chatSessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    byId("chat-input").value = "";
    appendChatMessage(turn.user_message);
    appendChatMessage(turn.assistant_message);
    if (turn.pending_action) appendPendingAction(turn.pending_action);
    byId("chat-transcript").scrollTop = byId("chat-transcript").scrollHeight;
    byId("chat-status").textContent = "Saved to your conversation.";
    loadChatSessions();
  } catch (error) {
    setError("chat-error", error.message);
    byId("chat-status").textContent = "Message could not be completed.";
    if (state.chatSessionId) openChatSession(state.chatSessionId);
  } finally {
    sendButton.disabled = !state.user;
  }
}

byId("login-toggle").addEventListener("click", () => byId("login-panel").classList.toggle("hidden"));
byId("logout-button").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
  clearSignedIn();
});
byId("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("login-error");
  const email = byId("email-input").value.trim();
  const password = byId("password-input").value;
  try {
    const user = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    byId("password-input").value = "";
    setSignedIn(user);
    renderCart();
  } catch (error) {
    state.credentials = null;
    setError("login-error", error.message);
  }
});
byId("filter-form").addEventListener("submit", (event) => { event.preventDefault(); loadMenu(); });
byId("refresh-menu").addEventListener("click", loadMenu);
byId("refresh-orders").addEventListener("click", loadOrders);
byId("place-order").addEventListener("click", placeOrder);
byId("menu-editor").addEventListener("submit", saveMenuItem);
byId("document-upload").addEventListener("submit", uploadPolicyDocument);
byId("clear-editor").addEventListener("click", resetEditor);
byId("save-status").addEventListener("click", updateOrderStatus);
const newChatButton = byId("new-chat");
if (newChatButton) newChatButton.addEventListener("click", createChatSession);
const chatForm = byId("chat-form");
if (chatForm) chatForm.addEventListener("submit", sendChatMessage);

renderCart();
loadMenu();

const openChat = byId("open-chat");
const closeChat = byId("close-chat");
const assistantWidget = byId("assistant-widget");
if (openChat && assistantWidget) {
  openChat.addEventListener("click", () => {
    const willOpen = assistantWidget.classList.contains("hidden");
    assistantWidget.classList.toggle("hidden", !willOpen);
    openChat.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) {
      const chatInput = byId("chat-input");
      if (chatInput) chatInput.focus();
    }
  });
}
if (closeChat && assistantWidget && openChat) {
  closeChat.addEventListener("click", () => {
    assistantWidget.classList.add("hidden");
    openChat.setAttribute("aria-expanded", "false");
  });
}

(async () => {
  try {
    const user = await api("/api/auth/me");
    setSignedIn(user);
  } catch (_) {}
})();
