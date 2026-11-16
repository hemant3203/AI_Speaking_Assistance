/**
 * Renders a lucide icon named by the API. A curated map rather than lucide's full `icons` export,
 * which would add every icon to the bundle. An unknown name falls back to a neutral icon.
 */
import {
  Activity, Award, BadgeCheck, Book, BookOpen, Brain, Briefcase, Calendar, CalendarCheck, CalendarDays, CircleCheck, Clock,
  Coffee, Compass, Crown, Drama, Dumbbell, Ear, Feather, Flag, Flame, Footprints, Gauge, Gem, Goal, GraduationCap, Heart,
  Hourglass, Infinity as InfinityIcon, Layers, Library, Lightbulb, Medal, Megaphone, MessageCircle, MessagesSquare, Mic,
  MicVocal, Moon, Mountain, Music, Palette, PenLine, Presentation, Repeat, Rocket, RotateCcw, Scale, Shield, ShieldCheck, Shuffle, Smile,
  Snowflake, Sparkle, Sparkles, Star, Sun, Sunrise, Swords, Target, ThumbsUp, Timer, TrendingUp, Trophy, User, UserRound,
  Users, Volume2, Waves, Wind, Zap, AudioLines, Glasses, HandHeart, Theater, Shapes, PartyPopper, Gavel,
} from 'lucide-react';

const ICONS = {
  Activity, Award, BadgeCheck, Book, BookOpen, Brain, Briefcase, Calendar, CalendarCheck, CalendarDays, CircleCheck, Clock,
  Coffee, Compass, Crown, Drama, Dumbbell, Ear, Feather, Flag, Flame, Footprints, Gauge, Gem, Goal, GraduationCap, Heart,
  Hourglass, Infinity: InfinityIcon, Layers, Library, Lightbulb, Medal, Megaphone, MessageCircle, MessagesSquare, Mic,
  MicVocal, Moon, Mountain, Music, Palette, PenLine, Presentation, Repeat, Rocket, RotateCcw, Scale, Shield, ShieldCheck, Shuffle, Smile,
  Snowflake, Sparkle, Sparkles, Star, Sun, Sunrise, Swords, Target, ThumbsUp, Timer, TrendingUp, Trophy, User, UserRound,
  Users, Volume2, Waves, Wind, Zap, AudioLines, Glasses, HandHeart, Theater, Shapes, PartyPopper, Gavel,
};

/** Accepts "MessageCircle" or "message-circle", in case the API uses the kebab-case name. */
const normalize = (name = '') =>
  name
    .split(/[-_\s]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');

export function DynamicIcon({ name, fallback: Fallback = Award, ...props }) {
  const Icon = ICONS[normalize(name)] ?? Fallback;
  return <Icon aria-hidden="true" {...props} />;
}
