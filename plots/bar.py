import matplotlib.pyplot
import numpy

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 

# plot a histogram of the frequency of each question
def plot_bar_model_performance(LP_O4_mean=None, LP_O4_variance=None, LP_O9_mean=None, LP_O9_variance=None, LLM_O4_mean=None, LLM_O4_variance=None, LLM_O9_mean=None, LLM_O9_variance=None):
    categories = ['O9 (Full)', 'O4']
    values1 = [LP_O9_mean, LP_O4_mean]  # First set of values
    values2 = [LLM_O9_mean, LLM_O4_mean]  # Second set of values

    # Define the width of the bars
    bar_width = 0.35

    # Create an array representing the index for each category
    x = numpy.arange(len(categories))
    ax = matplotlib.pyplot.subplot(1,1,1)

    # Plotting the bars
    ax.bar(x - bar_width/2, values1, width=bar_width, label=r'$\mathcal{B}^{LP}$', color=cmap(.25))
    ax.bar(x + bar_width/2, values2, width=bar_width, label=r'$\mathcal{B}^{LP + LLM}$', color=cmap(.75), hatch="x", edgecolor="white")#, linewidth=3

    ax.errorbar(x - bar_width/2, values1, yerr=[LP_O9_variance, LP_O4_variance], fmt='none', capsize=0, color='#404040', linewidth=5)
    ax.errorbar(x + bar_width/2, values2, yerr=[LLM_O9_variance, LLM_O4_variance], fmt='none', capsize=0, color='#404040', linewidth=5)

    # Adding labels, title, and legend
    ax.set_xlabel('Belief State Model $\mathcal{B}$')
    ax.set_ylabel(r'Score of $\beta^{robot}$ w.r.t. $\beta^{human}$')
    ax.set_ylim([0, 1.0])
    ax.set_yticks(ticks=[0, .25, .5, .75, 1], labels=["", "25%", "50%", "75%", "100%"])
    ax.set_xlim([-0.5, 1.5])
    ax.set_xticks(x, categories)  # Set the x-axis labels to the categories
    
    legend = ax.legend(loc="upper right")
    legend.get_frame().set_linewidth(0)  # Remove legend border
    legend.get_frame().set_facecolor('none')  # Remove legend background color

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()
