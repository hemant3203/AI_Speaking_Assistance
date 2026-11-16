/** Rewards: badges to chase, the sparks shop, and a ledger of what was earned. */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Award, Check, Lock, ReceiptText, ShoppingBag } from 'lucide-react';
import { equipCoach, fetchActivity, fetchBadges, fetchShop, purchaseItem } from '../api/gamification';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { useProfile } from '../components/layout/AppLayout';
import { BadgeCard } from '../components/gamification/BadgeCard';
import { SparksAmount } from '../components/gamification/Progress';
import { Banner } from '../components/ui/Banner';
import { Button } from '../components/ui/Button';
import { DynamicIcon } from '../components/ui/DynamicIcon';
import { PageHeader } from '../components/ui/PageHeader';
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States';
import { Tabs } from '../components/ui/Tabs';
import { dateTime } from '../lib/format';

const TABS = [
  { id: 'badges', label: 'Badges' },
  { id: 'shop', label: 'Shop' },
  { id: 'activity', label: 'Activity' },
];

const CATEGORY_NAMES = { streaks: 'Streaks', streak: 'Streaks', volume: 'Volume', skill: 'Skill', variety: 'Variety', challenge: 'Challenges', level: 'Level' };

function ListSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-2">
      {Array.from({ length: 6 }, (_, index) => (
        <Skeleton key={index} className="h-28 rounded-[var(--radius-card)]" />
      ))}
    </div>
  );
}

function BadgesTab() {
  const { data, loading, error, reload } = useApi(fetchBadges, []);
  if (loading) return <ListSkeleton />;
  if (error) return <ErrorState error={error} title="We couldn't load your badges" onRetry={reload} />;
  if (!data.items.length) {
    return (
      <EmptyState icon={Award} title="No badges to show yet" action={<Button to="/practice">Step into the spotlight</Button>}>
        Badges appear as you practise.
      </EmptyState>
    );
  }

  const groups = new Map();
  data.items.forEach((badge) => {
    if (!groups.has(badge.category)) groups.set(badge.category, []);
    groups.get(badge.category).push(badge);
  });
  const unlocked = data.items.filter((badge) => badge.unlocked).length;

  return (
    <div className="flex flex-col gap-8">
      <p className="text-ink-soft">
        You've earned <span className="font-semibold text-ink">{unlocked}</span> of {data.items.length} badges.
      </p>
      {[...groups.entries()].map(([category, badges]) => (
        <section key={category}>
          <h3 className="mb-3 text-xl font-bold capitalize">{CATEGORY_NAMES[category] ?? category}</h3>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {/* Earned first, then whichever locked badge is closest to done. */}
            {[...badges]
              .sort((a, b) => Number(b.unlocked) - Number(a.unlocked) || b.progress / (b.target || 1) - a.progress / (a.target || 1))
              .map((badge) => (
                <BadgeCard key={badge.id} badge={badge} />
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ShopItem({ item, busy, onBuy, onEquip }) {
  const isCoach = item.kind === 'coach';
  return (
    <li className={`card flex flex-col p-5 ${item.equipped ? 'border-amber' : ''}`}>
      <div className="flex items-start gap-3">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-raised text-ink-soft">
          <DynamicIcon name={item.icon} fallback={ShoppingBag} className="size-6" />
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="font-sans text-base font-semibold tracking-normal">{item.name}</h4>
          <p className="mt-0.5 text-sm text-ink-soft">{item.description}</p>
        </div>
      </div>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        {isCoach && item.owned ? (
          <span className="text-sm text-ink-muted">Unlocked</span>
        ) : (
          item.price === 0 ? <span className="text-lg font-semibold text-mint">Free</span> : <SparksAmount amount={item.price} className="text-lg font-semibold" />
        )}
        {isCoach && item.equipped && (
          <span className="inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-ink">
            <Check aria-hidden="true" className="size-4 text-mint" />
            Your coach
          </span>
        )}
        {isCoach && item.owned && !item.equipped && (
          <Button variant="secondary" size="sm" loading={busy} onClick={() => onEquip(item)}>
            Make my coach
          </Button>
        )}
        {(!isCoach || !item.owned) && (
          <Button variant="secondary" size="sm" loading={busy} disabled={!item.can_buy} onClick={() => onBuy(item)} icon={item.can_buy ? undefined : Lock}>
            Buy
          </Button>
        )}
      </div>
      {!item.can_buy && item.reason && !item.owned && <p className="mt-2 text-xs text-ink-muted">{item.reason}</p>}
      {!item.can_buy && item.reason && !isCoach && item.owned && <p className="mt-2 text-xs text-ink-muted">{item.reason}</p>}
    </li>
  );
}

function ShopTab() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const { reloadProfile } = useProfile();
  const { data, loading, error, reload } = useApi(fetchShop, []);
  const [busyId, setBusyId] = useState(null);

  if (loading) return <ListSkeleton />;
  if (error && !data) return <ErrorState error={error} title="We couldn't load the shop" onRetry={reload} />;

  const buy = async (item) => {
    setBusyId(item.id);
    try {
      await purchaseItem(item.id);
      toast.success(`${item.name} is yours.`);
      await Promise.all([reload(), reloadProfile()]);
    } catch (err) {
      toast.error(err.code === 'insufficient_sparks' ? `You need ${item.price} sparks for that. Practice earns more.` : err.message);
      reload();
    } finally {
      setBusyId(null);
    }
  };

  const equip = async (item) => {
    setBusyId(item.id);
    try {
      const { user: next } = await equipCoach(item.id);
      setUser(next ?? { ...user, equipped_coach: item.id });
      toast.success(`${item.name} will coach your next session.`);
      await reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const consumables = data.items.filter((item) => item.kind !== 'coach');
  const coaches = data.items.filter((item) => item.kind === 'coach');

  return (
    <div className="flex flex-col gap-8">
      <p className="flex items-center gap-2 text-ink-soft">
        Your balance:
        <SparksAmount amount={data.sparks} className="font-display text-2xl font-bold text-ink" />
      </p>
      {user?.is_admin && <Banner tone="info" title="Admin account">Everything here is free for you, and you have no daily practice limit.</Banner>}
      {consumables.length > 0 && (
        <section>
          <h3 className="mb-1 text-xl font-bold">Keep your streak safe</h3>
          <p className="mb-3 text-sm text-ink-soft">A freeze covers a missed day automatically, so one busy day doesn't undo your run.</p>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {consumables.map((item) => (
              <ShopItem key={item.id} item={item} busy={busyId === item.id} onBuy={buy} onEquip={equip} />
            ))}
          </ul>
        </section>
      )}
      {coaches.length > 0 && (
        <section>
          <h3 className="mb-1 text-xl font-bold">Choose your coach</h3>
          <p className="mb-3 text-sm text-ink-soft">Each coach has a different voice and a different way of giving feedback.</p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {coaches.map((item) => (
              <ShopItem key={item.id} item={item} busy={busyId === item.id} onBuy={buy} onEquip={equip} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ActivityTab() {
  const { data, loading, error, reload } = useApi(() => fetchActivity(20), []);
  if (loading) return <ListSkeleton />;
  if (error) return <ErrorState error={error} title="We couldn't load your activity" onRetry={reload} />;
  if (!data.items.length) {
    return (
      <EmptyState icon={ReceiptText} title="No activity yet" action={<Button to="/practice">Step into the spotlight</Button>}>
        Everything you earn and spend will be listed here.
      </EmptyState>
    );
  }
  return (
    <ul className="card divide-y divide-line px-4 sm:px-5">
      {data.items.map((item, index) => (
        <li key={`${item.created_at}${index}`} className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0">
            <p className="font-medium">{item.reason}</p>
            <p className="text-sm text-ink-muted">{dateTime(item.created_at)}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-0.5 text-sm font-semibold sm:flex-row sm:gap-3">
            {item.xp !== 0 && item.xp !== null && item.xp !== undefined && <span className="text-mint">{item.xp > 0 ? '+' : ''}{item.xp} XP</span>}
            {item.sparks !== 0 && item.sparks !== null && item.sparks !== undefined && <SparksAmount amount={item.sparks > 0 ? `+${item.sparks}` : item.sparks} />}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function RewardsPage() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const active = TABS.some((tab) => tab.id === requested) ? requested : 'badges';

  return (
    <>
      <PageHeader title="Rewards" description="What you've earned, and what you could spend it on." />
      <Tabs label="Rewards sections" tabs={TABS} active={active} onChange={(tab) => setParams(tab === 'badges' ? {} : { tab }, { replace: true })}>
        {active === 'badges' && <BadgesTab />}
        {active === 'shop' && <ShopTab />}
        {active === 'activity' && <ActivityTab />}
      </Tabs>
    </>
  );
}
