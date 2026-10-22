/** A page-shaped placeholder shown while a PDF or one of its pages loads. */
export default function PageSkeleton({ width, aspect }: { width: number; aspect: number }) {
    return (
        <div
            className="animate-pulse rounded-sm bg-gray-800 motion-reduce:animate-none"
            style={{ width, height: Math.round(width * aspect) }}
        />
    );
}
