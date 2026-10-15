#!/usr/bin/env node
// Media discovery and local delivery for design agents. Node 22+, no npm dependencies.
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash, randomUUID } from 'node:crypto';
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';

const exec = promisify(execFile);
const UA = 'oil-ui-curate-media/2.0 (Powered by Poly Haven)';
const KINDS = ['all', 'texture', 'design', 'photo', 'blueprint', 'map', 'plate', 'science', 'video'];
const PREFIX = { polyhaven: 'T', vam: 'V', loc: 'L', wellcome: 'W', nasa: 'N' };
const EXAMPLE = 'node scripts/curate-media.mjs search "wood" --kind texture --limit 6';
const HELP = `常用命令：
  ${EXAMPLE}
  node scripts/curate-media.mjs search "bridge" --kind blueprint --sheet --dir candidates
  node scripts/curate-media.mjs search "earth" --kind video --limit 4
  node scripts/curate-media.mjs preview V1,T2 --sheet --dir candidates
  node scripts/curate-media.mjs fetch V1,T2 --dir assets --sheet
  node scripts/curate-media.mjs fetch T2 --maps all --resolution 1k --dir assets
  node scripts/curate-media.mjs fetch "https://example.org/image.jpg" --out assets/image.jpg --note "来源说明"

用法：node curate-media.mjs <search|preview|fetch> <关键词或编号/URL> [选项]
  search "<关键词>"      搜索并返回 JSON；建议使用信源的英文关键词
  preview <编号,...>     从缓存制作候选联系表，也可传图片 URL
  fetch <编号,...>       批量下载；也可传一个或多个 HTTP(S) URL（URL 含逗号时单独传入）

  --kind <类别>         ${KINDS.join('|')}；默认 all
  --limit <1..30>        总结果数，默认 6；all 交错分配各信源
  --resolution <分辨率>  贴图 JPG：1k|2k|4k|8k，默认 1k，缺失时返回实际可用分辨率
  --maps <名称,...>     fetch 贴图：diffuse|roughness|normal|all；默认 diffuse
  --dir <目录>          下载/联系表目录，默认 assets
  --out <文件>          单文件下载路径，与 --dir 互斥；已有文件不会覆盖
  --sheet               search/preview 出 HTML 候选联系表；fetch 出本地联系表并完整解码检查
  --cache <文件>        默认当前工作目录 .curate-cache.json；跨命令使用同一缓存
  --refresh             search 忽略 24 小时的 Poly Haven 目录缓存
  --timeout <毫秒>      单个 API 请求超时，默认 12000
  --download-timeout <毫秒> 每文件下载超时，默认 180000；可设 1000..900000
  --max-mb <1..2048>     每文件下载上限，默认 256 MB
  --video-size <版本>   medium|small|preview|orig，默认 medium；失败时回退较小版本并记录原因
  --note <说明>         fetch 附加来源说明；URL 下载的权利状态记为未核实
  --help, -h            打印帮助；参数可用 --名字=值 或 --名字 值

信源与类别：texture=Poly Haven 无缝材质；design=V&A + Poly Haven 3D 模型预览；
photo=LOC + NASA；blueprint=LOC hh/HABS-HAER 测绘图；map=LOC maps；
plate=Wellcome；science=NASA + Wellcome；video=NASA；all 覆盖以上类别。
贴图 imageUrl/textureUrl 是真实 Diffuse JPG；previewUrl 是渲染预览；
textureMaps 提供 Diffuse/Roughness/OpenGL Normal 直链、大小与 MD5。
模型返回渲染预览及 glTF 文件/依赖清单，fetch 默认只下载模型预览图。
编号持续累加，同一素材保留原编号；清除缓存后编号重新开始。
标准输出是 JSON，进度/错误在标准错误。部分成功在 errors 中列出，仍保留有效结果；
全部信源失败或下载有失败时返回码 1。正常零匹配返回码 0。
HTML 联系表打开后显示真实图片宽高和加载失败；远程预览不会下载视频。
下载默认检查传输长度、签名、贴图 MD5；有 ffprobe 时检查实际宽高。
--sheet 及视频 poster 需要 ffmpeg/ffprobe；缺少时保留下载并明确报告未完成项。
所有成功下载及视频首帧 poster 自动记入同目录 SOURCES.md。
馆藏与 NASA 权利按记录/官方条款输出，不将整个信源标为可自由商用。`;

function usage(message) { throw new Error(`${message}\n示例：${EXAMPLE}\n批量下载：node scripts/curate-media.mjs fetch V1,T2 --dir assets --sheet\n全部选项：node scripts/curate-media.mjs --help`); }
export function parseArgs(argv) {
  const [command, ...args] = argv;
  if (!command || command === '--help' || command === '-h' || args.includes('--help') || args.includes('-h')) return { help: true };
  if (!['search', 'fetch', 'preview'].includes(command)) usage(`未知命令 ${command}`);
  const allowed = {
    search: ['kind', 'limit', 'resolution', 'dir', 'sheet', 'cache', 'refresh', 'timeout'],
    preview: ['dir', 'sheet', 'cache'],
    fetch: ['dir', 'out', 'sheet', 'cache', 'maps', 'resolution', 'timeout', 'max-mb', 'note', 'video-size', 'download-timeout'],
  }[command];
  const flags = ['sheet', 'refresh'];
  const opts = {}, positional = [];
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg.startsWith('-')) { positional.push(arg); continue; }
    const match = arg.match(/^--([^=]+)(?:=(.*))?$/);
    if (!match || !allowed.includes(match[1])) usage(`不支持 ${arg}；${command} 支持：${allowed.map(k => '--' + k).join(' ')}`);
    const [, key, inline] = match;
    if (key in opts) usage(`选项 --${key} 只能写一次`);
    if (flags.includes(key)) {
      if (inline !== undefined) usage(`--${key} 是不带值的开关`);
      opts[key] = true;
    } else {
      const value = inline ?? args[++i];
      if (!value || value.startsWith('--')) usage(`--${key} 缺少值`);
      opts[key] = value;
    }
  }
  if (!positional.length || !positional.join(' ').trim()) usage(`${command} 缺少关键词、编号或 URL`);
  if (opts.out && opts.dir) usage('--out 与 --dir 不能同时使用');
  opts.kind ??= 'all';
  if (!KINDS.includes(opts.kind)) usage(`--kind 应为 ${KINDS.join('|')}`);
  for (const [key, fallback, min, max] of [['limit', 6, 1, 30], ['timeout', 12000, 1000, 120000], ['max-mb', 256, 1, 2048], ['download-timeout', 180000, 1000, 900000]]) {
    opts[key] = Number(opts[key] ?? fallback);
    if (!Number.isInteger(opts[key]) || opts[key] < min || opts[key] > max) usage(`--${key} 应为 ${min}..${max} 的整数`);
  }
  opts.resolution ??= '1k';
  if (!['1k', '2k', '4k', '8k'].includes(opts.resolution)) usage('--resolution 应为 1k|2k|4k|8k');
  opts['video-size'] ??= 'medium';
  if (!['medium', 'small', 'preview', 'orig'].includes(opts['video-size'])) usage('--video-size 应为 medium|small|preview|orig');
  opts.maps = (opts.maps ?? 'diffuse').split(',');
  if (opts.maps.includes('all') && opts.maps.length === 1) opts.maps = ['diffuse', 'roughness', 'normal'];
  if (opts.maps.some(k => !['diffuse', 'roughness', 'normal'].includes(k))) usage('--maps 应为 diffuse,roughness,normal 或 all');
  opts.maps = [...new Set(opts.maps)];
  opts.cache = path.resolve(opts.cache ?? '.curate-cache.json');
  opts.dir = path.resolve(opts.dir ?? (opts.out ? path.dirname(opts.out) : 'assets'));
  return { command, positional, opts };
}

const https = value => String(value).replace(/^http:\/\//, 'https://').replace(/^\/\//, 'https://');
function httpUrl(value) {
  const u = new URL(value);
  if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) throw new Error('仅支持不带凭据的 HTTP(S) URL');
  return u.href;
}
const apiUrl = (base, params) => { const u = new URL(base); for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v)); return u.href; };
async function json(url, opts) {
  const res = await fetch(httpUrl(url), { headers: { 'User-Agent': UA, Accept: 'application/json' }, signal: AbortSignal.timeout(opts.timeout) });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.json();
}
async function pool(values, fn, concurrency = 3) {
  const output = new Array(values.length); let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, values.length) }, async () => {
    while (cursor < values.length) { const i = cursor++; try { output[i] = { status: 'fulfilled', value: await fn(values[i], i) }; } catch (reason) { output[i] = { status: 'rejected', reason }; } }
  }));
  return output;
}
const emptyCache = () => ({ version: 1, items: {}, catalogues: {} });
async function readCache(file) {
  try {
    const data = JSON.parse(await fs.readFile(file, 'utf8'));
    if (data.version !== 1 || !data.items || !data.catalogues) throw new Error('格式或版本不支持');
    return data;
  } catch (e) {
    if (e.code === 'ENOENT') return emptyCache();
    throw new Error(`缓存 ${file} 无法读取：${e.message}；请用 --cache 指定新文件`);
  }
}
// Serialize read/modify/write across concurrent agent processes; network calls stay outside the lock.
async function updateCache(file, fn) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const lock = file + '.lock'; const deadline = Date.now() + 5000;
  while (true) {
    try { await fs.mkdir(lock); break; } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      if (Date.now() > deadline) throw new Error(`缓存正在使用：${lock}；若上次进程已退出，可移除锁目录后重试`);
      await new Promise(resolve => setTimeout(resolve, 60));
    }
  }
  const temp = file + '.' + randomUUID() + '.tmp';
  try {
    const data = await readCache(file); const result = await fn(data);
    await fs.writeFile(temp, JSON.stringify(data)); await fs.rename(temp, file); return result;
  } finally { await fs.rm(temp, { force: true }); await fs.rmdir(lock); }
}
async function catalogue(type, opts) {
  const data = await readCache(opts.cache); const cached = data.catalogues[type];
  if (!opts.refresh && cached && Date.now() - cached.time < 86400000) return cached.data;
  const fresh = await json(`https://api.polyhaven.com/assets?t=${type}`, opts);
  await updateCache(opts.cache, c => { c.catalogues[type] = { time: Date.now(), data: fresh }; });
  return fresh;
}
export function selectMap(files, keys, resolution) {
  for (const key of keys) {
    const group = files[key]; if (!group) continue;
    const available = Object.keys(group).filter(r => group[r]?.jpg?.url).sort((a, b) => parseInt(a) - parseInt(b));
    const r = available.includes(resolution) ? resolution : available.filter(r => parseInt(r) <= parseInt(resolution)).at(-1) ?? available[0];
    if (r) return { ...group[r].jpg, resolution: r, channel: key };
  }
  return null;
}
async function resolveTexture(item, opts) {
  const files = await json(`https://api.polyhaven.com/files/${encodeURIComponent(item.sourceId)}`, opts);
  const textureMaps = {
    diffuse: selectMap(files, ['Diffuse', 'diff', 'Color', 'col'], opts.resolution),
    roughness: selectMap(files, ['Rough', 'rough', 'Roughness'], opts.resolution),
    normal: selectMap(files, ['nor_gl', 'Normal', 'normal'], opts.resolution),
  };
  if (!textureMaps.diffuse) throw new Error(`${item.sourceId} 没有可用 Diffuse JPG`);
  return { ...item, textureMaps, textureUrl: textureMaps.diffuse.url, imageUrl: textureMaps.diffuse.url, normalConvention: 'OpenGL', tiling: '查看 previewUrl 并检查重复边缘；部分材质仅单轴重复' };
}
async function searchPoly(query, limit, opts, type = 'textures') {
  const data = await catalogue(type, opts), terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const ranked = Object.entries(data).map(([slug, meta]) => {
    const hay = [slug.replaceAll('_', ' '), meta.name, meta.description, meta.category, ...(meta.categories ?? []), ...(meta.tags ?? [])].join(' ').toLowerCase();
    return { slug, meta, score: terms.reduce((n, t) => n + Number(hay.includes(t)), 0) };
  }).filter(x => x.score > 0).sort((a, b) => b.score - a.score).slice(0, limit);
  const out = await pool(ranked, async ({ slug, meta }) => {
    const previewUrl = `https://cdn.polyhaven.com/asset_img/thumbs/${encodeURIComponent(slug)}.png?width=768`;
    const item = { provider: 'polyhaven', sourceId: slug, kind: type === 'textures' ? 'texture' : 'model', title: meta.name ?? slug, detail: (meta.categories ?? []).join(', '), license: 'CC0', licenseUrl: 'https://polyhaven.com/license', attribution: [Object.keys(meta.authors ?? {}).join(', '), 'Powered by Poly Haven'].filter(Boolean).join(' · '), pageUrl: `https://polyhaven.com/a/${encodeURIComponent(slug)}`, previewUrl, imageUrl: previewUrl };
    if (type === 'textures') return resolveTexture(item, opts);
    const files = await json(`https://api.polyhaven.com/files/${encodeURIComponent(slug)}`, opts);
    const model = files.gltf?.[opts.resolution]?.gltf ?? Object.values(files.gltf ?? {})[0]?.gltf;
    return { ...item, modelFile: model ?? null, previewType: 'rendered-image' };
  });
  const errors = out.flatMap((r, i) => r.status === 'rejected' ? [`${ranked[i].slug}: ${r.reason.message}`] : []);
  return { items: out.filter(r => r.status === 'fulfilled').map(r => r.value), errors };
}
function iiifBase(value) { return value?.replace(/\/info\.json(?:\?.*)?$/, '').replace(/\/full\/.*$/, '').replace(/\/$/, ''); }
async function searchVam(query, limit, opts) {
  const data = await json(apiUrl('https://api.vam.ac.uk/v2/objects/search', { q: query, images_exist: 1, page_size: limit }), opts);
  return (data.records ?? []).flatMap(r => {
    const base = iiifBase(r._images?._iiif_image_base_url ?? r._images?._primary_thumbnail ?? (r._primaryImageId ? `https://framemark.vam.ac.uk/collections/${r._primaryImageId}` : null));
    if (!base) return [];
    return [{ provider: 'vam', sourceId: r.systemNumber, kind: 'design', title: r._primaryTitle || r.objectType || r.systemNumber, detail: [r.objectType, r._primaryMaker?.name, r._primaryDate, r._primaryPlace].filter(Boolean).join(' · '), license: 'V&A terms: permitted non-commercial uses only; commercial/home-page/high-resolution publication requires licensing', licenseUrl: 'https://www.vam.ac.uk/info/va-websites-terms-conditions', attribution: `© Victoria and Albert Museum, London (${r.systemNumber})`, pageUrl: `https://collections.vam.ac.uk/item/${r.systemNumber}`, iiifInfoUrl: `${base}/info.json`, imageUrl: `${base}/full/!1600,1600/0/default.jpg`, previewUrl: `${base}/full/!400,400/0/default.jpg` }];
  });
}
async function searchWellcome(query, limit, opts, kind = 'plate') {
  const data = await json(apiUrl('https://api.wellcomecollection.org/catalogue/v2/images', { query, pageSize: limit, include: 'source.contributors' }), opts);
  return (data.results ?? []).flatMap(r => {
    const loc = r.locations?.find(x => x.locationType?.id === 'iiif-image') ?? r.thumbnail;
    const base = iiifBase(loc?.url); if (!base) return [];
    const people = (r.source?.contributors ?? []).map(c => c.agent?.label).filter(Boolean);
    return [{ provider: 'wellcome', sourceId: r.id, kind, title: r.source?.title ?? r.id, detail: people.join(', '), license: loc.license?.label ?? 'Rights not specified; check item', licenseUrl: loc.license?.url ?? `https://wellcomecollection.org/works/${r.source?.id}`, attribution: [...people, loc.credit || 'Wellcome Collection'].join(' · '), pageUrl: `https://wellcomecollection.org/works/${r.source?.id}`, iiifInfoUrl: `${base}/info.json`, imageUrl: `${base}/full/!1600,1600/0/default.jpg`, previewUrl: `${base}/full/!400,400/0/default.jpg` }];
  });
}
function locItem(row, kind, imageUrl, previewUrl, sourceId, pageUrl) {
  const rights = row.item?.rights_advisory ?? row.item?.rights_information ?? row.rights ?? 'Rights not specified in search; check Rights & Access on item page';
  return { provider: 'loc', sourceId, kind, title: row.title ?? 'Library of Congress', detail: [row.date, ...(row.contributor ?? row.contributors ?? [])].filter(Boolean).join(' · '), license: Array.isArray(rights) ? rights.join(' ') : rights, licenseUrl: pageUrl, attribution: row.item?.repository ?? 'Library of Congress', pageUrl, imageUrl: https(imageUrl), previewUrl: https(previewUrl ?? imageUrl) };
}
async function searchLoc(query, limit, opts, kind = 'photo') {
  if (kind === 'blueprint') return searchBlueprint(query, limit, opts);
  const data = await json(apiUrl(`https://www.loc.gov/${kind === 'map' ? 'maps' : 'photos'}/`, { q: query, fo: 'json', c: Math.min(limit * 2, 60) }), opts);
  return (data.results ?? []).filter(r => !r.access_restricted).flatMap(r => {
    const urls = (r.image_url ?? []).filter(u => /\.(jpe?g|png)(?:[?#]|$)/i.test(u));
    if (!urls.length) return [];
    const best = urls.at(-1).split('#')[0], page = https(r.url || r.id);
    return [locItem(r, kind, best, (urls[1] ?? urls[0]).split('#')[0], r.id ?? page, page)];
  }).slice(0, limit);
}
async function searchBlueprint(query, limit, opts) {
  // hh includes photographs and surveys. Only /sheet/ images are measured drawings.
  const data = await json(apiUrl('https://www.loc.gov/collections/historic-american-buildings-landscapes-and-engineering-records/', { q: `${query} drawings`, fo: 'json', at: 'results', c: Math.min(limit * 3, 60) }), opts);
  return (data.results ?? []).flatMap(row => {
    const resource = (row.resources ?? []).find(r => /\/sheet\//.test(r.image ?? ''));
    const image = resource?.image ?? (row.image_url ?? []).find(u => /\/sheet\//.test(u));
    if (!image) return [];
    const preview = new URL(https(image), 'https://www.loc.gov').href.split('#')[0];
    // LOC service derivative suffixes: _150px thumbnail, r medium, v large.
    const full = preview.replace(/_150px\.jpg$/, 'v.jpg').replace(/r\.jpg$/, 'v.jpg');
    const page = https(resource?.url ?? row.url ?? row.id);
    return [locItem(row, 'blueprint', full, preview.replace(/_150px\.jpg$/, 'r.jpg'), page, page)];
  }).slice(0, limit);
}
export function selectNasaFile(urls, type, videoSize = 'medium') {
  const candidates = urls.filter(u => type === 'video' ? /\.(mp4|mov)(?:\?|$)/i.test(u) : /\.(jpe?g|png)(?:\?|$)/i.test(u));
  const rank = type === 'video' ? [`~${videoSize}.`, ...['~medium.', '~small.', '~mobile.', '~preview.', '~orig.'].filter(x => x !== `~${videoSize}.`)] : ['~orig.', '~large.', '~medium.', '~small.', '~thumb.'];
  return candidates.sort((a, b) => {
    const score = u => { const i = rank.findIndex(t => u.includes(t)); return i < 0 ? 99 : i; };
    return score(a) - score(b);
  })[0];
}
async function resolveNasa(item, opts) {
  const data = await json(item.manifestUrl, opts);
  const urls = Array.isArray(data) ? data : (data.collection?.items ?? []).map(r => r.href);
  const url = selectNasaFile(urls, item.mediaType, opts['video-size']);
  if (!url) throw new Error(`${item.sourceId} 无可下载的 ${item.mediaType} 文件`);
  const alternates = item.mediaType === 'video' ? ['preview', 'small', 'mobile'].map(size => urls.find(u => u.includes(`~${size}.`) && /\.mp4$/i.test(u))).filter(Boolean) : ['large', 'medium', 'small'].map(size => urls.find(u => u.includes(`~${size}.`) && /\.(jpe?g|png)$/i.test(u))).filter(Boolean);
  return { ...item, downloadCandidates: [...new Set([url, ...alternates].map(https))], ...(item.mediaType === 'video' ? { videoUrl: https(url) } : { imageUrl: https(url) }) };
}
async function searchNasa(query, limit, opts, mediaType = 'image', kind = 'science') {
  const data = await json(apiUrl('https://images-api.nasa.gov/search', { q: query, media_type: mediaType, page_size: mediaType === 'video' ? Math.min(limit * 3, 100) : limit }), opts);
  return (data.collection?.items ?? []).flatMap(row => {
    const r = row.data?.[0]; if (!r) return [];
    const image = row.links?.find(l => l.render === 'image' && l.rel === 'preview')?.href ?? row.links?.find(l => l.render === 'image')?.href;
    if (!image) return [];
    if (mediaType === 'video' && /animation|visualization|simulation|computer.generated|rendering/i.test([r.title, ...(r.keywords ?? [])].join(' '))) return [];
    const thirdParty = /copyright|©|all rights reserved/i.test([r.description, r.photographer, r.secondary_creator].join(' '));
    return [{ provider: 'nasa', sourceId: r.nasa_id, kind, mediaType: r.media_type, title: r.title ?? r.nasa_id, detail: [r.center, r.date_created, r.description?.replace(/<[^>]*>/g, '').slice(0, 500)].filter(Boolean).join(' · '), license: thirdParty ? 'Third-party rights mentioned; check item credits' : 'NASA media usage guidelines; generally not subject to US copyright; verify third-party credits', licenseUrl: 'https://www.nasa.gov/nasa-brand-center/images-and-media/', attribution: ['NASA', r.center, r.photographer, r.secondary_creator].filter(Boolean).join(' · '), pageUrl: `https://images.nasa.gov/details/${encodeURIComponent(r.nasa_id)}`, imageUrl: https(image), previewUrl: https(image), manifestUrl: https(row.href ?? `https://images-api.nasa.gov/asset/${encodeURIComponent(r.nasa_id)}`) }];
  }).slice(0, limit);
}
export function interleave(groups, limit) {
  const out = [], seen = new Set();
  for (let i = 0; groups.some(g => i < g.length) && out.length < limit; i++) {
    for (const group of groups) {
      const item = group[i]; if (!item) continue;
      const key = `${item.provider}:${item.sourceId}`;
      if (seen.has(key)) continue; seen.add(key); out.push(item);
      if (out.length === limit) break;
    }
  }
  return out;
}
async function remember(items, opts) {
  return updateCache(opts.cache, cache => items.map(item => {
    const existing = Object.values(cache.items).find(x => x.provider === item.provider && x.sourceId === item.sourceId);
    const prefix = PREFIX[item.provider];
    const next = Math.max(0, ...Object.keys(cache.items).filter(k => k.startsWith(prefix)).map(k => Number(k.slice(1)) || 0)) + 1;
    const ref = existing?.ref ?? prefix + next;
    const result = { ...existing, ...item, ref, cachedAt: new Date().toISOString() }; cache.items[ref] = result; return result;
  }));
}
async function runSearch(query, opts) {
  const per = opts.kind === 'all' ? Math.max(2, Math.ceil(opts.limit / 5)) : opts.limit;
  const jobs = {
    texture: [['polyhaven/textures', () => searchPoly(query, per, opts)]],
    design: [['vam', () => searchVam(query, per, opts)], ['polyhaven/models', () => searchPoly(query, per, opts, 'models')]],
    photo: [['loc/photos', () => searchLoc(query, per, opts)], ['nasa/images', () => searchNasa(query, per, opts, 'image', 'photo')]],
    blueprint: [['loc/hh', () => searchLoc(query, per, opts, 'blueprint')]],
    map: [['loc/maps', () => searchLoc(query, per, opts, 'map')]],
    plate: [['wellcome', () => searchWellcome(query, per, opts)]],
    science: [['nasa/science', () => searchNasa(query, per, opts)], ['wellcome/science', () => searchWellcome(query, per, opts, 'science')]],
    video: [['nasa/video', () => searchNasa(query, per, opts, 'video', 'video')]],
  };
  const selected = opts.kind === 'all' ? [...jobs.texture, ...jobs.design.slice(0, 1), ...jobs.photo.slice(0, 1), ...jobs.plate, ...jobs.science.slice(0, 1), ...jobs.blueprint, ...jobs.map, ...jobs.video, ...jobs.design.slice(1)] : jobs[opts.kind];
  const results = await Promise.allSettled(selected.map(async ([label, fn]) => {
    const start = Date.now(); const value = await fn(); const items = Array.isArray(value) ? value : value.items;
    console.error(`[curate-media] ${label}: ${items.length} 项 (${Date.now() - start}ms)`);
    return { items, errors: value.errors ?? [] };
  }));
  const errors = results.flatMap((r, i) => r.status === 'rejected' ? [{ source: selected[i][0], message: r.reason.message }] : r.value.errors.map(message => ({ source: selected[i][0], message })));
  const items = await remember(interleave(results.filter(r => r.status === 'fulfilled').map(r => r.value.items), opts.limit), opts);
  const sheet = opts.sheet ? await writeSheet(items, opts.dir, true) : undefined;
  return { query, kind: opts.kind, count: items.length, cache: opts.cache, items, errors, ...(sheet ? { sheet } : {}), failed: results.every(r => r.status === 'rejected') || (!items.length && errors.length > 0) };
}
async function targets(positional, opts) {
  const tokens = positional.flatMap(x => /^https?:\/\//i.test(x) ? [x] : x.split(','));
  const cache = await readCache(opts.cache);
  return [...new Set(tokens)].map(token => {
    if (/^[TVLWN]\d+$/i.test(token)) {
      const item = cache.items[token.toUpperCase()];
      if (!item) usage(`缓存中没有 ${token}；先 search，或用 --cache 选择原缓存`);
      return item;
    }
    try {
      const url = httpUrl(token);
      // A pasted result URL retains its source metadata whenever the workspace knows it.
      const known = Object.values(cache.items).find(x => [x.imageUrl, x.videoUrl, ...Object.values(x.textureMaps ?? {}).map(m => m?.url)].includes(url));
      return { ...known, directUrl: url, imageUrl: url, title: known?.title ?? path.basename(new URL(url).pathname), provider: known?.provider ?? 'url', license: known?.license ?? 'Rights not verified (direct URL)', attribution: known?.attribution ?? 'Source supplied by user', pageUrl: known?.pageUrl ?? url, previewUrl: url };
    } catch { usage(`无效编号或 URL：${token}`); }
  });
}
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
async function writeSheet(items, dir, remote) {
  await fs.mkdir(dir, { recursive: true });
  const cards = items.map(item => {
    const src = remote ? item.previewUrl ?? item.imageUrl : item.poster ?? item.saved;
    const href = remote ? src : src && path.relative(dir, src).split(path.sep).map(encodeURIComponent).join('/');
    const image = href && !/\.(mp4|mov|webm)(?:\?|$)/i.test(href) ? `<img src="${escapeHtml(href)}" alt="${escapeHtml(item.title)}"><p class="size">加载中…</p>` : '<p>没有图片预览；请查看下载结果</p>';
    return `<article>${image}<h2>${escapeHtml(item.ref ?? 'URL')} · ${escapeHtml(item.map ?? item.kind)} · ${escapeHtml(item.title)}</h2><p>${escapeHtml(item.license)}</p><p>${escapeHtml(item.attribution)}</p><a href="${escapeHtml(item.pageUrl)}">来源记录</a>${item.integrity ? `<p>${escapeHtml(item.integrity)} · ${item.width ?? '?'} × ${item.height ?? '?'}</p>` : ''}</article>`;
  }).join('\n');
  const file = path.join(dir, remote ? 'candidates.html' : 'sheet.html');
  const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>素材候选联系表</title><style>body{font:15px/1.5 system-ui;margin:24px;background:#eee;color:#222}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}article{background:white;padding:16px;overflow-wrap:anywhere}img{width:100%;height:240px;object-fit:contain}h2{font-size:17px;line-height:1.4}.error{color:#a00}</style><h1>素材候选 · ${items.length} 项</h1><p>${remote ? '远程预览：宽高为预览文件尺寸，原图尺寸在下载结果中。' : '本地素材：解码结果与真实宽高见各项说明。'}</p><main>${cards}</main><script>for(const img of document.images){const label=img.nextElementSibling;function check(){label.textContent=img.naturalWidth?img.naturalWidth+' × '+img.naturalHeight:'加载失败';if(!img.naturalWidth)label.className='error'}img.addEventListener('load',check);img.addEventListener('error',check);if(img.complete)check()}</script></html>`;
  await fs.writeFile(file, html); return file;
}
async function hasTool(name) { try { await exec(name, ['-version'], { timeout: 5000, maxBuffer: 100000 }); return true; } catch { return false; } }
export function sniff(buffer) {
  if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return { ext: '.jpg', video: false };
  if (buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) return { ext: '.png', video: false };
  if (buffer.toString('ascii', 0, 6).match(/^GIF8[79]a$/)) return { ext: '.gif', video: false };
  if (buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP') return { ext: '.webp', video: false };
  if (buffer.toString('ascii', 4, 8) === 'ftyp') return { ext: buffer.toString('ascii', 8, 12).startsWith('qt') ? '.mov' : '.mp4', video: true };
  if (buffer.subarray(0, 4).equals(Buffer.from([0x1a, 0x45, 0xdf, 0xa3]))) return { ext: '.webm', video: true };
  throw new Error('响应不是支持的图片或视频；可能是 HTML、JSON 错误页或损坏的文件');
}
async function download(url, temp, opts, expected) {
  const res = await fetch(httpUrl(url), { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(opts['download-timeout']) });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  const max = opts['max-mb'] * 1024 * 1024, length = Number(res.headers.get('content-length'));
  if (length > max) { await res.body?.cancel(); throw new Error(`文件超过 --max-mb ${opts['max-mb']}`); }
  if (/text\/html|application\/json/.test(res.headers.get('content-type') ?? '')) { await res.body?.cancel(); throw new Error('响应是错误页或元数据，不是媒体文件'); }
  const handle = await fs.open(temp, 'wx'); let bytes = 0, head = Buffer.alloc(0); const md5 = createHash('md5');
  try {
    for await (const chunk of res.body) {
      bytes += chunk.length; if (bytes > max) throw new Error(`文件超过 --max-mb ${opts['max-mb']}`);
      if (head.length < 32) head = Buffer.concat([head, Buffer.from(chunk)]).subarray(0, 32);
      md5.update(chunk); await handle.writeFile(chunk);
    }
  } finally { await handle.close(); }
  if (!bytes || (length && !res.headers.get('content-encoding') && bytes !== length)) throw new Error('文件为空或传输不完整');
  if (expected?.size && bytes !== expected.size) throw new Error(`文件大小不符：${bytes}，预期 ${expected.size}`);
  const digest = md5.digest('hex'); if (expected?.md5 && digest !== expected.md5) throw new Error('MD5 校验失败');
  return { bytes, md5: digest, ...sniff(head) };
}
async function inspect(file, tools, full) {
  if (!tools.ffprobe) return { integrity: 'signature-and-length-only', warnings: ['缺少 ffprobe，尚未检查真实宽高'] };
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,codec_name:format=duration', '-of', 'json', file], { timeout: 20000, maxBuffer: 100000 });
  const data = JSON.parse(stdout), stream = data.streams?.[0];
  if (!stream?.width || !stream?.height) throw new Error('没有可解码的图像/视频流');
  if (full && tools.ffmpeg) await exec('ffmpeg', ['-nostdin', '-v', 'error', '-xerror', '-i', file, '-map', '0:v:0', '-f', 'null', '-'], { timeout: 120000, maxBuffer: 1000000 });
  return { width: stream.width, height: stream.height, codec: stream.codec_name, duration: Number(data.format?.duration) || undefined, integrity: full && tools.ffmpeg ? 'full-decode' : 'probed', warnings: full && !tools.ffmpeg ? ['缺少 ffmpeg，尚未完整解码'] : [] };
}
const safeName = s => String(s ?? 'media').replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 90) || 'media';
// Reserve the destination atomically; repeated downloads get suffixes instead of overwriting.
async function deliver(temp, wanted, explicit = false) {
  for (let i = 0; i < 1000; i++) {
    const p = path.parse(wanted), file = i ? path.join(p.dir, `${p.name}-${i}${p.ext}`) : wanted;
    try { await fs.copyFile(temp, file, fs.constants.COPYFILE_EXCL); return file; } catch (e) { if (e.code !== 'EEXIST') throw e; if (explicit) throw new Error(`文件已存在：${file}；请换一个 --out 文件名`); }
  }
  throw new Error('文件名冲突过多');
}
const mdText = s => String(s ?? '').replace(/[\r\n]+/g, ' ').replace(/[`\[\]<>]/g, '');
async function logSources(records, note) {
  const groups = new Map();
  for (const r of records) {
    const dir = path.dirname(r.saved); if (!groups.has(dir)) groups.set(dir, []);
    const line = `- \`${path.basename(r.saved)}\` — ${mdText(r.ref ?? r.provider)} · ${mdText(r.title)}${r.map ? ' · ' + r.map : ''}\n  - Source: ${r.pageUrl}\n  - Download: ${r.url}\n  - License: ${mdText(r.license)} (${r.licenseUrl ?? r.pageUrl})\n  - Credit: ${mdText(r.attribution)}${note ? '\n  - Note: ' + mdText(note) : ''}\n`;
    groups.get(dir).push(line);
    if (r.poster) groups.get(dir).push(`- \`${path.basename(r.poster)}\` — first-frame poster derived from \`${path.basename(r.saved)}\`; same license and credit as above.\n`);
  }
  for (const [dir, lines] of groups) await fs.appendFile(path.join(dir, 'SOURCES.md'), lines.join('\n') + '\n');
}
async function resolveIIIF(item, opts) {
  const info = await json(item.iiifInfoUrl, opts);
  if (!info.width || !info.height) throw new Error('IIIF 没有有效的原图尺寸');
  const base = iiifBase(item.iiifInfoUrl);
  const imageUrl = Math.max(info.width, info.height) <= 1600 ? `${base}/full/full/0/default.jpg` : `${base}/full/!1600,1600/0/default.jpg`;
  return { ...item, imageUrl, originalWidth: info.width, originalHeight: info.height };
}
async function runFetch(items, opts) {
  if (opts.out && (items.length !== 1 || (items[0].kind === 'texture' && !items[0].directUrl && opts.maps.length > 1))) usage('--out 只支持单文件；批量拉取用 --dir assets');
  await fs.mkdir(opts.dir, { recursive: true });
  const tools = { ffmpeg: await hasTool('ffmpeg'), ffprobe: await hasTool('ffprobe') };
  const tasks = [], errors = [], records = [];
  for (let item of items) {
    try {
      if (!item.directUrl && item.kind === 'texture') item = await resolveTexture(item, opts);
      else if (!item.directUrl && item.provider === 'nasa') item = await resolveNasa(item, opts);
      else if (!item.directUrl && item.iiifInfoUrl) item = await resolveIIIF(item, opts);
      if (item.kind === 'texture' && !item.directUrl) {
        for (const map of opts.maps) {
          const file = item.textureMaps[map];
          if (!file) { errors.push({ ref: item.ref, map, message: `没有可用 ${map} JPG` }); continue; }
          tasks.push({ item, map, url: file.url, expected: file });
        }
      } else tasks.push({ item, url: item.directUrl ?? item.videoUrl ?? item.imageUrl });
    } catch (e) { errors.push({ ref: item.ref, message: e.message }); }
  }
  const settled = await pool(tasks, async ({ item, map, url, expected }) => {
    const temp = path.join(opts.dir, `.${randomUUID()}.part`); let result;
    try {
      let received; const recovery = [];
      const candidates = item.directUrl ? [url] : item.downloadCandidates ?? [url];
      for (const candidate of candidates.slice(0, 3)) {
        try { received = await download(candidate, temp, opts, expected); url = candidate; break; }
        catch (e) { recovery.push(`${candidate}: ${e.message}`); await fs.rm(temp, { force: true }); }
      }
      if (!received) throw new Error(recovery.join('; '));
      const inspection = await inspect(temp, tools, opts.sheet);
      const filename = `${safeName(item.ref ?? item.provider)}-${safeName(item.sourceId ?? item.title)}${map ? '-' + map + '-' + expected.resolution : ''}${received.ext}`;
      const out = opts.out ? path.resolve(opts.out) : path.join(opts.dir, filename);
      if (opts.out && ![received.ext, ...(received.ext === '.jpg' ? ['.jpeg'] : [])].includes(path.extname(out).toLowerCase())) throw new Error(`--out 后缀与实际文件格式不一致，应为 ${received.ext}`);
      const saved = await deliver(temp, out, Boolean(opts.out));
      result = { ref: item.ref, provider: item.provider, sourceId: item.sourceId, kind: item.kind, title: item.title, map, resolution: expected?.resolution, url, saved, pageUrl: item.pageUrl, license: item.license, licenseUrl: item.licenseUrl, attribution: item.attribution, originalWidth: item.originalWidth, originalHeight: item.originalHeight, ...(map === 'normal' ? { normalConvention: item.normalConvention } : {}), ...received, ...inspection };
      if (recovery.length) result.warnings.push(`已回退到可用版本；之前失败：${recovery.join('; ')}`);
      if (received.video) {
        if (!tools.ffmpeg) result.warnings.push('缺少 ffmpeg，poster 未生成');
        else {
          const posterTemp = path.join(opts.dir, `.${randomUUID()}.jpg`);
          try {
            await exec('ffmpeg', ['-nostdin', '-v', 'error', '-xerror', '-i', saved, '-frames:v', '1', '-q:v', '2', posterTemp], { timeout: 30000, maxBuffer: 100000 });
            result.poster = await deliver(posterTemp, saved.replace(/\.[^.]+$/, '-poster.jpg'));
          } catch (e) { result.warnings.push(`poster 失败：${e.message}`); }
          finally { await fs.rm(posterTemp, { force: true }); }
        }
      }
      console.error(`[curate-media] ${item.ref ?? 'URL'}${map ? '/' + map : ''}: ${received.bytes} bytes → ${saved}`);
      return result;
    } finally { await fs.rm(temp, { force: true }); }
  });
  settled.forEach((r, i) => { if (r.status === 'fulfilled') records.push(r.value); else errors.push({ ref: tasks[i].item.ref, url: tasks[i].url, message: r.reason.message }); });
  await logSources(records, opts.note);
  for (const r of records) if ((opts.sheet && r.integrity !== 'full-decode') || (r.video && !r.poster)) errors.push({ ref: r.ref, saved: r.saved, message: r.warnings.join('; ') || '检查或 poster 未完成' });
  const sheet = opts.sheet ? await writeSheet(records, opts.dir, false) : undefined;
  return { count: records.length, files: records, errors, ...(sheet ? { sheet } : {}), ...(records.length === 1 ? { saved: records[0].saved, bytes: records[0].bytes } : {}), failed: errors.length > 0 };
}
export async function main(argv = process.argv.slice(2)) {
  const parsed = parseArgs(argv); if (parsed.help) { console.log(HELP); return; }
  const { command, positional, opts } = parsed; const start = Date.now(); let result;
  if (command === 'search') result = await runSearch(positional.join(' ').trim(), opts);
  else {
    const items = await targets(positional, opts);
    result = command === 'fetch' ? await runFetch(items, opts) : { count: items.length, items, sheet: await writeSheet(items, opts.dir, true) };
  }
  const { failed, ...output } = result;
  console.log(JSON.stringify({ ...output, elapsedMs: Date.now() - start }, null, 2));
  if (failed) process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(err => { console.error(`[curate-media] ${err.message}`); process.exitCode = 1; });
}
