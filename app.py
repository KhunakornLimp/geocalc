from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import SubmitField
from math import pi, sin, radians, sqrt
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import CubicSpline
matplotlib.use('Agg')  # Set the backend before importing pyplot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'


class BareCalculator(FlaskForm):
    submit = SubmitField('Calculate')


def calculate_flotation_profit(price_per_ton_metal, charge_per_ton_conc,
                               feed_flowrate, feed_grade, recoveries,
                               final_conc_grades):
    profits = []
    metal_feed_flowrate = feed_flowrate * feed_grade / 100
    for i in range(len(recoveries)):
        metal_final_conc_flowrate = \
            metal_feed_flowrate * recoveries[i] / 100
        final_conc_flowrate = \
            metal_final_conc_flowrate / (final_conc_grades[i] / 100)
        # Revenues from selling metal
        # Treatment charges from selling concentrates
        revenue = metal_final_conc_flowrate * price_per_ton_metal
        charge = final_conc_flowrate * charge_per_ton_conc
        profits.append(revenue - charge)
    return profits


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/permeability', methods=['GET', 'POST'])
def calculate_permeability():
    calculator = BareCalculator()
    permeability = None
    if calculator.validate_on_submit():
        form = request.form
        radius = float(form['radius']) / 100  # Convert to m
        length = float(form['length']) / 100  # Convert to m
        angle = radians(float(form['angle']))
        flowrate = float(form['flowrate']) / 10**6  # Convert to m^3/s
        density = float(form['density'])
        viscosity = float(form['viscosity'])
        inlet_pressure = float(form['inlet_pressure'])
        outlet_pressure = float(form['outlet_pressure'])
        # Calculate permeability
        darcy_velocity = flowrate / (pi * radius**2)
        gravity = 9.81 * sin(angle)
        pressure_gradient = (inlet_pressure - outlet_pressure) / length
        permeability = (darcy_velocity * viscosity) / \
            (pressure_gradient + (density * gravity)) * 10**12  # in Darcy

    else:
        print(calculator.errors)

    return render_template('permeability.html',
                           form=calculator,
                           permeability=permeability)


@app.route('/flow-under-gravity', methods=['GET', 'POST'])
def flow_under_g():
    calculator = BareCalculator()
    permeability, density1, density2, viscosity1, darcy_velocity = \
        None, None, None, None, None
    if calculator.validate_on_submit():
        form = request.form
        permeability = float(form['permeability'])
        density1 = float(form['density1'])
        density2 = float(form['density2'])
        viscosity1 = float(form['viscosity1'])
        # Calculate hydraulic conductivity (1-phase)
        # or Darcy velocity (2-phase)
        darcy_velocity = \
            abs(permeability / viscosity1 * (density1 - density2) * 9.81)
        darcy_velocity *= 10**-12

    else:
        print(calculator.errors)

    return render_template('flow_under_g.html',
                           form=calculator,
                           density1=density1,
                           density2=density2,
                           darcy_velocity=darcy_velocity)


@app.route('/leverett', methods=['GET', 'POST'])
def leverett():
    calculator = BareCalculator()
    saturations, capillary_pressures_L, capillary_pressures_F = [], [], []
    if calculator.validate_on_submit():
        form = request.form
        interfacial_tension_L = float(form['interfacial_tension_L'])
        porosity_L = float(form['porosity_L'])
        permeability_L = float(form['permeability_L'])

        # Get the capillary pressure in the lab and saturation values
        i = 1
        while True:
            S_name = f'saturation_{i}'
            Pc_lab_name = f'capillary_pressure_L_{i}'
            if S_name in request.form and Pc_lab_name in request.form:
                S = float(request.form[S_name])
                saturations.append(S)
                Pc_lab = float(request.form[Pc_lab_name])
                capillary_pressures_L.append(Pc_lab)
                i += 1
            else:
                break

        interfacial_tension_F = float(form['interfacial_tension_F'])
        porosity_F = float(form['porosity_F'])
        permeability_F = float(form['permeability_F'])

        # Calculate the proportional constant A (Pc_field = A * Pc_lab)
        interfacial_tension_ratio = \
            interfacial_tension_F / interfacial_tension_L
        porosity_ratio = porosity_F / porosity_L
        permeability_ratio = permeability_F / permeability_L
        A = interfacial_tension_ratio * \
            sqrt(porosity_ratio / permeability_ratio)

        # Calculate capillary pressures in the field
        for Pc_lab in capillary_pressures_L:
            capillary_pressures_F.append(A * Pc_lab)

    else:
        print(calculator.errors)

    if capillary_pressures_F:
        plt.plot([min(saturations), max(saturations)], [0, 0], '--', c='gray')
        plt.plot(saturations, capillary_pressures_L, label='Lab', marker='.')
        plt.plot(saturations, capillary_pressures_F, label='Field', marker='.')
        plt.xlabel('Saturation')
        plt.ylabel('Capillary pressure (Pa)')
        plt.legend()
        plt.savefig('static/leverett.png', bbox_inches='tight')
        plt.close()

    return render_template(
        'leverett.html',
        form=calculator,
        saturations=saturations,
        capillary_pressures_L=capillary_pressures_L,
        capillary_pressures_F=capillary_pressures_F,
    )


@app.route('/optimal-flotation', methods=['GET', 'POST'])
def optimal_flotation():
    calculator = BareCalculator()
    recoveries, final_conc_grades, profits = [], [], []
    if calculator.validate_on_submit():
        form = request.form
        price_per_ton_metal = float(form['price_per_ton_metal'])
        charge_per_ton_conc = float(form['charge_per_ton_conc'])
        feed_flowrate = float(form['feed_flowrate'])
        feed_grade = float(form['feed_grade'])
        recoveries_and_final_conc_grades = {}

        # Get the recovery and final concentrate grade values
        i = 1
        while True:
            recovery_name = f'recovery_{i}'
            final_conc_grade_name = f'final_conc_grade_{i}'
            if recovery_name in form and final_conc_grade_name in form:
                recovery = float(form[recovery_name])
                final_conc_grade = float(form[final_conc_grade_name])
                recoveries_and_final_conc_grades[recovery] = final_conc_grade
                i += 1
            else:
                break

        recoveries_and_final_conc_grades = \
            dict(sorted(recoveries_and_final_conc_grades.items()))
        recoveries = list(recoveries_and_final_conc_grades.keys())
        final_conc_grades = list(recoveries_and_final_conc_grades.values())

        profits = calculate_flotation_profit(price_per_ton_metal,
                                             charge_per_ton_conc,
                                             feed_flowrate,
                                             feed_grade,
                                             recoveries,
                                             final_conc_grades)

    else:
        print(calculator.errors)

    # The status of the maximum profit - unknown error by default
    status = "Unknown error!"
    if profits:
        fig, axs = plt.subplots(1, 2, figsize=(14, 4))
        # Grade-recovery curve - natural cubic spline interpolation
        axs[0].plot(recoveries, final_conc_grades, 'r.')
        interpolant = CubicSpline(recoveries, final_conc_grades)
        interpolated_recoveries = \
            np.linspace(min(recoveries), max(recoveries), 1000)
        interpolated_final_conc_grades = interpolant(interpolated_recoveries)
        axs[0].plot(interpolated_recoveries,
                    interpolated_final_conc_grades,
                    'r-')
        axs[0].set(
            xlabel='Recovery (%)',
            ylabel='Grade of final concentrate (%)',
            title='Grade-recovery curve',
        )
        # Profit-recovery curve - interpolate based on grade-recovery curve
        axs[1].plot(recoveries, profits, 'r.')
        interpolated_profits = calculate_flotation_profit(
            price_per_ton_metal, charge_per_ton_conc,
            feed_flowrate, feed_grade,
            interpolated_recoveries, interpolated_final_conc_grades)
        axs[1].plot(interpolated_recoveries, interpolated_profits, 'r-')
        opt_pos = \
            np.where(interpolated_profits == max(interpolated_profits))[0][0]
        if opt_pos != 0 and opt_pos != 999:
            axs[1].plot(interpolated_recoveries[opt_pos],
                        interpolated_profits[opt_pos],
                        '*', c='#00ccff', markersize=10, label='Optimum')
            if max(interpolated_profits) <= 0:
                status = "Non-profitable operation!"
            else:
                status = "The maximum profit is approximately " + \
                    f"${max(interpolated_profits):.1f} per hour, " + \
                    "which can be achieved at a recovery of " + \
                    f"{interpolated_recoveries[opt_pos]:.2f}% and a grade " + \
                    f"of {interpolated_final_conc_grades[opt_pos]:.2f}%."
        elif opt_pos == 0:
            status = "A lower recovery could lead to a higher profit."
            if max(interpolated_profits) < 0:
                status += " However, it may not be profitable."
        else:  # opt_pos == 999
            status = "A higher recovery could lead to a higher profit."
            if max(interpolated_profits) < 0:
                status += " However, it may not be profitable."
        axs[1].set(
            xlabel='Recovery (%)',
            ylabel='Profit ($/hr)',
            title='Profit-recovery curve',
        )
        axs[1].legend()
        plt.savefig('static/flotation_curves.png', bbox_inches='tight')
        plt.close()

    return render_template(
        'optimal_flotation.html',
        form=calculator,
        recoveries=recoveries,
        final_conc_grades=final_conc_grades,
        profits=profits,
        status=status,
    )


@app.route('/partition-curve', methods=['GET', 'POST'])
def partition_curve():
    calculator = BareCalculator()
    representative_sizes, partition_numbers = [], []
    if calculator.validate_on_submit():
        form = request.form
        feed_flowrate = float(form['feed_flowrate'])
        coarse_flowrate = float(form['coarse_flowrate'])
        total_mass_recovery = coarse_flowrate / feed_flowrate
        upper_limit_sizes, percentages_in_feed, percentages_in_coarse = \
            [], [], []

        # Get the recovery and final concentrate grade values
        i = 1
        while True:
            # Check if the form has the required fields
            upper_limit_size_name = f'upper_limit_size_{i}'
            percentage_in_feed_name = f'percentage_in_feed_{i}'
            percentage_in_coarse_name = f'percentage_in_coarse_{i}'
            check = upper_limit_size_name in form
            check = check and percentage_in_feed_name in form
            check = check and percentage_in_coarse_name in form
            if check:
                upper_limit_sizes.append(float(form[upper_limit_size_name]))
                percentages_in_feed.append(
                    float(form[percentage_in_feed_name])
                )
                percentages_in_coarse.append(
                    float(form[percentage_in_coarse_name])
                )
                i += 1
            else:
                break

        for i in range(len(percentages_in_feed)):
            if i < len(percentages_in_feed) - 1:
                representative_sizes.append(
                    sqrt(upper_limit_sizes[i] * upper_limit_sizes[i+1])
                )
            else:
                representative_sizes.append(upper_limit_sizes[i] / 2)
            partition_numbers.append(total_mass_recovery *
                                     percentages_in_coarse[i] /
                                     percentages_in_feed[i])

    else:
        print(calculator.errors)

    bypass, cutsize = None, None
    if representative_sizes:
        # Find bypass and cutsize
        bypass = partition_numbers[-1]
        for i in range(len(partition_numbers) - 1):
            if partition_numbers[i] >= 0.5 and partition_numbers[i + 1] < 0.5:
                slope = (partition_numbers[i] - partition_numbers[i + 1]) / \
                    (representative_sizes[i] - representative_sizes[i + 1])
                cutsize = representative_sizes[i] + \
                    (0.5 - partition_numbers[i]) / slope
                break

        # Plot the partition curve
        plt.plot([min(representative_sizes), max(representative_sizes)],
                 [0.5, 0.5], '--', c='gray')
        plt.plot(representative_sizes, partition_numbers, '.-')
        plt.xlabel('Particle size (μm)')
        plt.ylabel('Partition number')
        plt.xscale("log")
        plt.title('Partition curve')
        plt.savefig('static/partition_curve.png', bbox_inches='tight')
        plt.close()

    return render_template('partition_curve.html',
                           form=calculator,
                           bypass=bypass,
                           cutsize=cutsize)


if __name__ == '__main__':
    app.run(debug=True)  # Add debug=True to run the app in debug mode
