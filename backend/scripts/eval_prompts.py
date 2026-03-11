"""
A/B тестирование промптов и калибровка оценщика.

Загружает эталонный датасет (data/calibration/expert_markup.json),
прогоняет через текущий Evaluator, считает Pearson correlation и MAE.

Запуск: python -m scripts.eval_prompts [--verbose]
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

CALIBRATION_FILE = Path(__file__).parent.parent / "data" / "calibration" / "expert_markup.json"


async def run_evaluation():
    verbose = "--verbose" in sys.argv

    if not CALIBRATION_FILE.exists():
        print(f"Файл не найден: {CALIBRATION_FILE}")
        sys.exit(1)

    with open(CALIBRATION_FILE) as f:
        dataset = json.load(f)

    print(f"Загружено {len(dataset)} эталонных оценок\n")

    from app.core.evaluator import evaluate_smart
    from app.core.schemas import EvaluateRequest

    results = []
    errors = 0

    for i, item in enumerate(dataset):
        try:
            req = EvaluateRequest(
                goal_text=item["goal_text"],
                position=item["position"],
                department=item["department"],
                quarter="2025-Q4",
            )
            smart = await evaluate_smart(req)

            expert = item["expert_scores"]
            expert_avg = sum(expert.values()) / len(expert)

            model_scores = {
                "S": smart.S.score, "M": smart.M.score, "A": smart.A.score,
                "R": smart.R.score, "T": smart.T.score,
            }
            model_avg = smart.smart_index

            per_criterion_mae = {
                k: abs(model_scores[k] - expert[k]) for k in "SMRT" + "A"
                if k in expert and k in model_scores
            }
            index_mae = abs(model_avg - expert_avg)

            results.append({
                "goal_text": item["goal_text"][:60],
                "expert_avg": expert_avg,
                "model_avg": model_avg,
                "index_mae": index_mae,
                "per_criterion": per_criterion_mae,
                "expert_type": item.get("expert_type"),
                "model_type": smart.goal_type,
                "type_match": item.get("expert_type") == smart.goal_type,
            })

            if verbose:
                print(f"[{i+1}/{len(dataset)}] {item['goal_text'][:50]}")
                print(f"  Expert: {expert_avg:.1f} | Model: {model_avg:.1f} | MAE: {index_mae:.2f}")
                print(f"  Type: expert={item.get('expert_type')} model={smart.goal_type}")
                print()

        except Exception as e:
            print(f"  ОШИБКА [{i+1}]: {e}")
            errors += 1

    if not results:
        print("Нет результатов для анализа")
        return

    # ─── Статистика ───────────────────────────────────────────────────────────────

    mae_index = sum(r["index_mae"] for r in results) / len(results)
    type_accuracy = sum(r["type_match"] for r in results) / len(results)

    # Pearson correlation
    expert_vals = [r["expert_avg"] for r in results]
    model_vals = [r["model_avg"] for r in results]
    n = len(expert_vals)
    mean_e = sum(expert_vals) / n
    mean_m = sum(model_vals) / n
    cov = sum((e - mean_e) * (m - mean_m) for e, m in zip(expert_vals, model_vals))
    std_e = (sum((e - mean_e) ** 2 for e in expert_vals) / n) ** 0.5
    std_m = (sum((m - mean_m) ** 2 for m in model_vals) / n) ** 0.5
    pearson = cov / (n * std_e * std_m) if std_e * std_m > 0 else 0

    # Per-criterion MAE
    crit_maes = {}
    for k in ["S", "M", "A", "R", "T"]:
        vals = [r["per_criterion"].get(k, 0) for r in results if k in r["per_criterion"]]
        crit_maes[k] = round(sum(vals) / len(vals), 3) if vals else 0

    # Worst predictions
    worst = sorted(results, key=lambda r: r["index_mae"], reverse=True)[:5]

    print("=" * 60)
    print("РЕЗУЛЬТАТЫ КАЛИБРОВКИ ПРОМПТОВ")
    print("=" * 60)
    print(f"\n{'Метрика':<30} {'Значение':>10}")
    print("-" * 42)
    print(f"{'Pearson correlation':<30} {pearson:>10.3f}")
    print(f"{'MAE (SMART-индекс)':<30} {mae_index:>10.3f}")
    print(f"{'Точность классификации типа':<30} {type_accuracy*100:>9.1f}%")
    print(f"{'Обработано успешно':<30} {len(results):>10}")
    print(f"{'Ошибок':<30} {errors:>10}")

    print(f"\n{'По критериям MAE':}")
    for k, v in crit_maes.items():
        bar = "█" * int(v * 20)
        print(f"  {k}: {v:.3f}  {bar}")

    print(f"\nТоп-5 худших предсказаний:")
    for r in worst:
        print(f"  MAE={r['index_mae']:.2f} | expert={r['expert_avg']:.1f} model={r['model_avg']:.1f}")
        print(f"    «{r['goal_text']}»")

    print("\n" + "=" * 60)

    # Оценка качества
    if pearson >= 0.85 and mae_index <= 0.5:
        print("✓ ОТЛИЧНОЕ качество промптов (Pearson≥0.85, MAE≤0.5)")
    elif pearson >= 0.7 and mae_index <= 0.8:
        print("~ ХОРОШЕЕ качество промптов (Pearson≥0.7, MAE≤0.8)")
    else:
        print("✗ Промпты требуют улучшения (Pearson<0.7 или MAE>0.8)")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
