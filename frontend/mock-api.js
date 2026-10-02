// In-browser stand-in for the Lambda API, used when ATHENA_API_URL is empty (static demo).
// Mirrors the backend: same routes, same JSON shapes, template planner + bag-of-words cosine.
(function () {
  const plans = {};
  let dataPromise;
  const data = () => (dataPromise ||= Promise.all([
    fetch('data/employees.json').then(r => r.json()),
    fetch('data/training_catalogue.json').then(r => r.json()),
  ]).then(([employees, catalogue]) => ({ employees, catalogue })));

  const now = () => new Date().toISOString().slice(0, 19) + 'Z';
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const audit = (p, action, by, note = '') => (p.audit ||= []).push({ at: now(), action, by, note });

  const bag = t => (t.toLowerCase().match(/[a-z0-9]+/g) || []).filter(w => w.length > 2)
    .reduce((v, w) => (v[w] = (v[w] || 0) + 1, v), {});
  const cosine = (a, b) => {
    let dot = 0, na = 0, nb = 0;
    for (const k in a) { dot += a[k] * (b[k] || 0); na += a[k] ** 2; }
    for (const k in b) nb += b[k] ** 2;
    return na && nb ? dot / Math.sqrt(na * nb) : 0;
  };

  function selectModules(emp, catalogue, k = 8) {
    const profile = bag(`${emp.role} in ${emp.team}. Skills: ${emp.skills.join(', ')}`);
    const mandatory = catalogue.filter(m => m.mandatory);
    const ranked = catalogue.filter(m => !m.mandatory)
      .map(m => [cosine(profile, bag(`${m.title}. ${m.description} Tags: ${m.tags.join(', ')}`)), m])
      .sort((a, b) => b[0] - a[0]).map(x => x[1]);
    return mandatory.concat(ranked.slice(0, k - mandatory.length));
  }

  function templatePlan(emp, modules) {
    const themes = ['Settle in & essentials', 'Team tools & systems', 'First contributions'];
    const days = ['Mon-Tue', 'Wed-Thu', 'Fri'];
    const weeks = themes.map((theme, i) => ({ week: i + 1, theme, items: [] }));
    modules.forEach((m, i) => {
      const w = m.mandatory ? 0 : Math.min(1 + (Math.floor(i / 3) % 2), 2);
      weeks[w].items.push({ moduleId: m.id, day: days[weeks[w].items.length % 3], goal: m.description, title: m.title, hours: m.hours, link: m.link });
    });
    return { summary: `A 3-week plan to help ${emp.name} ramp up as ${emp.role} in ${emp.team}.`, weeks };
  }

  const ok = body => ({ ok: true, status: 200, body });
  const fail = (status, message) => ({ ok: false, status, body: { message } });

  window.mockApi = async function (method, path, body) {
    await wait(450);
    const { employees, catalogue } = await data();
    let m;
    if (method === 'GET' && (m = path.match(/^\/employees\/(.+)$/))) {
      const emp = employees.find(e => e.employeeId === decodeURIComponent(m[1]).trim().toUpperCase());
      return emp ? ok(emp) : fail(404, `No employee found with ID ${m[1]}`);
    }
    if (method === 'POST' && path === '/plans') {
      const emp = employees.find(e => e.employeeId === String(body.employeeId).trim().toUpperCase());
      if (!emp) return fail(404, 'Employee not found');
      await wait(900);
      const modules = selectModules(emp, catalogue);
      const rec = { planId: crypto.randomUUID(), employeeId: emp.employeeId, employee: emp, plan: templatePlan(emp, modules),
        generatedBy: 'template (demo mode)', status: 'PENDING_REVIEW', version: 1, createdAt: now() };
      audit(rec, 'GENERATED', 'athena', `${modules.length} modules selected by cosine similarity (demo mode)`);
      plans[rec.planId] = rec;
      return ok(rec);
    }
    if ((m = path.match(/^\/plans\/([^/]+)$/))) {
      const rec = plans[m[1]];
      if (!rec) return fail(404, 'Plan not found');
      if (method === 'GET') return ok(rec);
      const decision = (body.decision || '').toUpperCase();
      if (!['APPROVED', 'REJECTED'].includes(decision)) return fail(400, 'decision must be APPROVED or REJECTED');
      rec.status = decision;
      audit(rec, decision, body.reviewer || 'HR reviewer', body.note || '');
      return ok(rec);
    }
    if (method === 'POST' && (m = path.match(/^\/plans\/([^/]+)\/send$/))) {
      const rec = plans[m[1]];
      if (!rec) return fail(404, 'Plan not found');
      if (!['APPROVED', 'SENT'].includes(rec.status)) return fail(409, 'Plan must be approved by HR before sending');
      rec.status = 'SENT';
      audit(rec, 'EMAIL_PREVIEWED', 'athena', rec.employee.email);
      return ok({ mode: 'preview', to: rec.employee.email, subject: `Welcome aboard, ${rec.employee.name.split(' ')[0]}! Your 3-week onboarding plan`, html: null, plan: rec });
    }
    return fail(404, 'Not found');
  };
})();
