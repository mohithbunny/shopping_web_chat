UI.renderHeader("login");

const params = new URLSearchParams(location.search);
const next = params.get("next");

function goAfterLogin(user) {
  // Only follow same-site paths for "next".
  if (next && next.startsWith("/") && !next.startsWith("//")) location.href = next;
  else location.href = user.role === "admin" ? "/admin.html" : "/";
}

if (Auth.isLoggedIn()) goAfterLogin(Auth.user);

const tabs = { login: document.getElementById("tab-login"), register: document.getElementById("tab-register") };
const forms = { login: document.getElementById("login-form"), register: document.getElementById("register-form") };

function showTab(name) {
  for (const key of Object.keys(tabs)) {
    tabs[key].setAttribute("aria-selected", key === name);
    forms[key].classList.toggle("hidden", key !== name);
  }
}
tabs.login.addEventListener("click", () => showTab("login"));
tabs.register.addEventListener("click", () => showTab("register"));

async function submit(form, errorEl, action) {
  const btn = form.querySelector("button[type=submit]");
  errorEl.classList.add("hidden");
  btn.disabled = true;
  try {
    const { access_token, user } = await action();
    Auth.save(access_token, user);
    goAfterLogin(user);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
}

forms.login.addEventListener("submit", (e) => {
  e.preventDefault();
  submit(forms.login, document.getElementById("login-error"), () =>
    Api.login(document.getElementById("login-email").value, document.getElementById("login-password").value));
});

forms.register.addEventListener("submit", (e) => {
  e.preventDefault();
  submit(forms.register, document.getElementById("register-error"), () =>
    Api.register(
      document.getElementById("reg-name").value,
      document.getElementById("reg-email").value,
      document.getElementById("reg-password").value,
    ));
});
