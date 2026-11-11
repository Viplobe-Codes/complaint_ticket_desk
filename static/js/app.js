const byId = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function statusClass(status) {
  if (status === "Closed") return "status-closed";
  if (status === "In progress") return "status-progress";
  return "status-open";
}

async function loadCategories() {
  const categories = await api("/api/categories");
  const select = byId("category-select");
  select.replaceChildren(new Option("Choose a category", ""));
  for (const category of categories) {
    select.add(new Option(`${category.name} — ${category.handler}`, category.cat_id));
  }
}

async function loadReports() {
  const report = await api("/api/reports/status");
  byId("stat-open").textContent = report.Open;
  byId("stat-progress").textContent = report["In progress"];
  byId("stat-closed").textContent = report.Closed;
  byId("stat-total").textContent = report.Open + report["In progress"] + report.Closed;
}

async function loadTickets() {
  const body = byId("ticket-list");
  body.replaceChildren();
  const filter = byId("status-filter").value;
  const query = filter ? `?status=${encodeURIComponent(filter)}` : "";
  try {
    const tickets = await api(`/api/warden/tickets${query}`);
    if (!tickets.length) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 5;
      cell.className = "empty-cell";
      cell.textContent = "No complaints match this filter yet.";
      return;
    }
    for (const ticket of tickets) {
      const row = body.insertRow();
      const idCell = row.insertCell();
      idCell.append(element("span", "ticket-id", `#${ticket.ticket_id}`));

      const studentCell = row.insertCell();
      studentCell.append(element("span", "", ticket.student_name));
      studentCell.append(element("span", "secondary", `Room ${ticket.room_no} · ${ticket.category}`));

      const issueCell = row.insertCell();
      issueCell.append(element("span", "issue-text", ticket.description));
      issueCell.title = ticket.description;

      const statusCell = row.insertCell();
      statusCell.append(element("span", `status-pill ${statusClass(ticket.status)}`, ticket.status));

      const actionCell = row.insertCell();
      if (ticket.status === "Closed") {
        actionCell.append(element("span", "closed-label", "Resolved"));
      } else {
        const next = ticket.status === "Open" ? "In progress" : "Closed";
        const button = element("button", "advance-button", `Move to ${next}`);
        button.type = "button";
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await api(`/api/warden/tickets/${ticket.ticket_id}/status`, {
              method: "PATCH", body: JSON.stringify({ status: next }),
            });
            await refreshDashboard();
          } catch (error) {
            window.alert(error.message);
            button.disabled = false;
            await loadTickets();
          }
        });
        actionCell.append(button);
      }
    }
  } catch (error) {
    const row = body.insertRow();
    const cell = row.insertCell();
    cell.colSpan = 5;
    cell.className = "empty-cell";
    cell.textContent = error.message;
  }
}

async function refreshDashboard() {
  await Promise.all([loadReports(), loadTickets()]);
}

byId("complaint-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = byId("submit-message");
  message.className = "feedback";
  message.textContent = "Submitting…";
  const fields = new FormData(form);
  const payload = Object.fromEntries(fields.entries());
  payload.cat_id = Number(payload.cat_id);
  try {
    const result = await api("/api/tickets", { method: "POST", body: JSON.stringify(payload) });
    message.textContent = `Complaint submitted. Your ticket number is #${result.ticket_id}.`;
    byId("ticket-number").value = result.ticket_id;
    form.reset();
    await refreshDashboard();
  } catch (error) {
    message.className = "feedback error";
    message.textContent = error.message;
  }
});

byId("track-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const ticketNumber = byId("ticket-number").value;
  const result = byId("ticket-result");
  result.className = "ticket-result empty-state";
  result.textContent = "Looking up ticket…";
  try {
    const ticket = await api(`/api/tickets/${encodeURIComponent(ticketNumber)}`);
    result.className = "ticket-result ticket-detail";
    result.replaceChildren();
    result.append(element("h3", "", `Ticket #${ticket.ticket_id}`));
    result.append(element("p", "", `Status: ${ticket.status}`));
    result.append(element("p", "", `${ticket.category} · handled by ${ticket.handler}`));
    result.append(element("p", "", ticket.description));
    result.append(element("p", "", `Submitted ${ticket.raised_at} · Room ${ticket.room_no}`));
  } catch (error) {
    result.className = "ticket-result empty-state";
    result.textContent = error.message;
  }
});

byId("status-filter").addEventListener("change", loadTickets);

Promise.all([loadCategories(), refreshDashboard()]).catch((error) => {
  byId("submit-message").className = "feedback error";
  byId("submit-message").textContent = `Could not connect to the API: ${error.message}`;
});
