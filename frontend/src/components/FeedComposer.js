import React, { useRef, useState } from "react";
import { api } from "../api";
import { toast } from "sonner";
import { X, Image as ImageIcon, Film, Loader2, Send, Sparkles } from "lucide-react";

const POST_KINDS = [
  { key: "update", label: "Update", color: "#CCFF00" },
  { key: "wip", label: "WIP", color: "#F5A623" },
  { key: "studio_photo", label: "Studio", color: "#7C3AED" },
  { key: "announcement", label: "News", color: "#00E5FF" },
  { key: "sold", label: "Sold", color: "#CCFF00" },
  { key: "commission", label: "Commission", color: "#7C3AED" },
  { key: "exhibition", label: "Exhibition", color: "#D4AF37" },
  { key: "behind_scenes", label: "BTS", color: "#FF6EC7" },
  { key: "event", label: "Event", color: "#00E5FF" },
];

/**
 * Full-screen composer modal for creating a studio post (feed post) without leaving /feed.
 * Supports body text (with @mentions), post-kind selection, and optional image OR video.
 */
export default function FeedComposer({ onClose, onCreated }) {
  const [kind, setKind] = useState("update");
  const [text, setText] = useState("");
  const [image, setImage] = useState(null); // { path, url }
  const [video, setVideo] = useState(null); // { path, url }
  const [uploading, setUploading] = useState(false);
  const [posting, setPosting] = useState(false);
  const imgRef = useRef(null);
  const vidRef = useRef(null);

  const uploadFile = async (file, kindType) => {
    if (!file) return;
    if (kindType === "image" && video) { toast.error("Remove the video first"); return; }
    if (kindType === "video" && image) { toast.error("Remove the image first"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const endpoint = kindType === "video" ? "/upload/video" : "/upload/image";
      const r = await api.post(endpoint, fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (kindType === "video") setVideo({ path: r.data.path, url: r.data.url });
      else setImage({ path: r.data.path, url: r.data.url });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!text.trim() && !image && !video) { toast.error("Add text, an image, or a video"); return; }
    setPosting(true);
    try {
      const payload = {
        kind,
        text: text.trim() || "—",
        image: image?.path || null,
        video: video?.path || null,
        pinned: false,
      };
      const r = await api.post("/posts", payload);
      toast.success("Posted");
      onCreated?.(r.data);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Post failed");
    }
    setPosting(false);
  };

  return (
    <div
      data-testid="feed-composer-modal"
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-3 md:p-6 overflow-y-auto"
      onClick={onClose}>
      <div
        className="bg-[#121214] border border-white/10 rounded-sm w-full max-w-xl my-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-white/8">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-[#CCFF00]" />
            <div className="label-caps">New Post</div>
          </div>
          <button data-testid="composer-close" onClick={onClose} className="text-zinc-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="p-4 space-y-4">
          {/* Kind chips */}
          <div className="flex gap-2 flex-wrap" data-testid="composer-kinds">
            {POST_KINDS.map((k) => {
              const active = k.key === kind;
              return (
                <button
                  type="button"
                  key={k.key}
                  data-testid={`composer-kind-${k.key}`}
                  onClick={() => setKind(k.key)}
                  className="label-caps text-xs px-3 py-1.5 rounded-full border transition-colors"
                  style={{
                    borderColor: active ? k.color : "rgba(255,255,255,0.12)",
                    background: active ? `${k.color}20` : "transparent",
                    color: active ? k.color : "#A1A1AA",
                  }}>
                  {k.label}
                </button>
              );
            })}
          </div>

          {/* Textarea */}
          <textarea
            data-testid="composer-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            maxLength={2000}
            placeholder="What are you working on? Use @name to tag other artists."
            className="w-full bg-white/[0.03] border border-white/12 rounded-sm px-3 py-3 outline-none focus:border-[#CCFF00] text-sm resize-none" />
          <div className="text-xs text-zinc-500 -mt-3 text-right">{text.length}/2000</div>

          {/* Media preview */}
          {image && (
            <div className="relative border border-white/8 rounded-sm overflow-hidden" data-testid="composer-image-preview">
              <img src={image.url?.startsWith("http") ? image.url : `${process.env.REACT_APP_BACKEND_URL}${image.url}`} alt="" className="w-full max-h-72 object-cover bg-black" />
              <button
                type="button"
                onClick={() => setImage(null)}
                className="absolute top-2 right-2 bg-black/60 border border-white/20 rounded-full p-1 hover:bg-black">
                <X size={12} />
              </button>
            </div>
          )}
          {video && (
            <div className="relative border border-white/8 rounded-sm overflow-hidden" data-testid="composer-video-preview">
              <video
                src={video.url?.startsWith("http") ? video.url : `${process.env.REACT_APP_BACKEND_URL}${video.url}`}
                controls
                playsInline
                className="w-full max-h-72 bg-black" />
              <button
                type="button"
                onClick={() => setVideo(null)}
                className="absolute top-2 right-2 bg-black/60 border border-white/20 rounded-full p-1 hover:bg-black">
                <X size={12} />
              </button>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between gap-2 pt-2 border-t border-white/8">
            <div className="flex gap-2">
              <label className="btn-ghost !py-2 !px-3 cursor-pointer flex items-center gap-1.5 text-xs">
                {uploading ? <Loader2 size={13} className="animate-spin" /> : <ImageIcon size={13} />}
                <span>Image</span>
                <input
                  ref={imgRef}
                  data-testid="composer-attach-image"
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => uploadFile(e.target.files?.[0], "image")} />
              </label>
              <label className="btn-ghost !py-2 !px-3 cursor-pointer flex items-center gap-1.5 text-xs">
                {uploading ? <Loader2 size={13} className="animate-spin" /> : <Film size={13} />}
                <span>Video</span>
                <input
                  ref={vidRef}
                  data-testid="composer-attach-video"
                  type="file"
                  accept="video/mp4,video/webm,video/quicktime"
                  className="hidden"
                  onChange={(e) => uploadFile(e.target.files?.[0], "video")} />
              </label>
            </div>
            <button
              type="submit"
              data-testid="composer-submit"
              disabled={posting || uploading || (!text.trim() && !image && !video)}
              className="btn-lime !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
              {posting ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
              Post
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
