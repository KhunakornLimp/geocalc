from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from math import pi, sin, radians, sqrt
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import CubicSpline
matplotlib.use('Agg')  # Set the backend before importing pyplot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'


class PermeabilityCalculator(FlaskForm):
    # Core properties
    radius = FloatField('Core cross-sectional radius (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    length = FloatField('Core length (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    # Fluid properties
    angle = FloatField('Flow direction (degrees)',
                       validators=[DataRequired(),
                                   NumberRange(min=-90, max=90)])
    flowrate = FloatField('Fluid flow rate (cm^3/s)',
                          validators=[DataRequired(), NumberRange(min=0)])
    density = FloatField('Fluid density (kg/m^3)',
                         validators=[NumberRange(min=0)],
                         default=1000)  # Default value for water
    viscosity = FloatField('Fluid viscosity (Pa.s)',
                           validators=[NumberRange(min=0)],
                           default=0.001)  # Default value for water
    inlet_pressure = FloatField('Fluid inlet pressure (Pa)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    outlet_pressure = FloatField('Fluid outlet pressure (Pa)',
                                 validators=[DataRequired(),
                                             NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


class FlowUnderGravity(FlaskForm):
    # Medium properties
    permeability = FloatField('Permeability (D)',
                              validators=[DataRequired(), NumberRange(min=0)])
    # Fluid properties
    density1 = FloatField('Fluid 1 density (kg/m^3)',
                          validators=[DataRequired(), NumberRange(min=0)])
    density2 = FloatField('Fluid 2 density (kg/m^3)',
                          validators=[NumberRange(min=0)],
                          default=0)
    viscosity1 = FloatField('Fluid 1 viscosity (Pa.s)',
                            validators=[DataRequired(), NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


class Leverett(FlaskForm):
    # In the lab (L)
    interfacial_tension_L = FloatField('Interfacial tension in the lab (mN/m)',
                                       validators=[DataRequired(),
                                                   NumberRange(min=0)])
    porosity_L = FloatField('Porosity in the lab',
                            validators=[DataRequired(),
                                        NumberRange(min=0, max=1)])
    permeability_L = FloatField('Permeability in the lab (D)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    # In the field (F)
    interfacial_tension_F = \
        FloatField('Interfacial tension in the field (mN/m)',
                   validators=[DataRequired(), NumberRange(min=0)])
    porosity_F = FloatField('Porosity in the field',
                            validators=[DataRequired(),
                                        NumberRange(min=0, max=1)])
    permeability_F = FloatField('Permeability in the field (D)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


class OptimalFlotation(FlaskForm):
    price_per_ton_metal = \
        FloatField('Price per ton of metal ($)',
                   validators=[DataRequired(), NumberRange(min=0)])
    charge_per_ton_conc = \
        FloatField('Treatment charge per ton of concentrate ($)',
                   validators=[DataRequired(), NumberRange(min=0)])
    feed_flowrate = \
        FloatField('Feed flowrate (tph)',
                   validators=[DataRequired(), NumberRange(min=0)])
    feed_grade = \
        FloatField('Feed grade (%)',
                   validators=[DataRequired(), NumberRange(min=0, max=100)])
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
    calculator = PermeabilityCalculator()
    permeability = None
    if calculator.validate_on_submit():
        radius = calculator.radius.data / 100  # Convert to m
        length = calculator.length.data / 100  # Convert to m
        angle = radians(calculator.angle.data)  # Convert to radians
        flowrate = calculator.flowrate.data / 10**6  # Convert to m^3/s
        density = calculator.density.data
        viscosity = calculator.viscosity.data
        inlet_pressure = calculator.inlet_pressure.data
        outlet_pressure = calculator.outlet_pressure.data
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
    calculator = FlowUnderGravity()
    darcy_velocity = None
    if calculator.validate_on_submit():
        permeability = calculator.permeability.data
        density1 = calculator.density1.data
        density2 = calculator.density2.data
        viscosity1 = calculator.viscosity1.data
        # Calculate hydraulic conductivity (1-phase)
        # or Darcy velocity (2-phase)
        darcy_velocity = \
            abs(permeability / viscosity1 * (density1 - density2) * 9.81)
        darcy_velocity *= 10**-12

    else:
        print(calculator.errors)

    return render_template('flow_under_g.html',
                           form=calculator,
                           darcy_velocity=darcy_velocity)


@app.route('/leverett', methods=['GET', 'POST'])
def leverett():
    calculator = Leverett()
    saturations, capillary_pressures_L, capillary_pressures_F = [], [], []
    if calculator.validate_on_submit():
        interfacial_tension_L = calculator.interfacial_tension_L.data
        porosity_L = calculator.porosity_L.data
        permeability_L = calculator.permeability_L.data
        S_and_Pc_lab = {}

        # Get the capillary pressure in the lab and saturation values
        i = 1
        while True:
            Pc_lab_name = f'capillary_pressure_L_{i}'
            S_name = f'saturation_{i}'

            if Pc_lab_name in request.form and S_name in request.form:
                Pc_lab = float(request.form[Pc_lab_name])
                S = float(request.form[S_name])
                S_and_Pc_lab[S] = Pc_lab
                i += 1
            else:
                break
        # TO DO: allow same saturation values but
        # different capillary pressures in the lab
        S_and_Pc_lab = dict(sorted(S_and_Pc_lab.items()))
        saturations = list(S_and_Pc_lab.keys())
        capillary_pressures_L = list(S_and_Pc_lab.values())

        interfacial_tension_F = calculator.interfacial_tension_F.data
        porosity_F = calculator.porosity_F.data
        permeability_F = calculator.permeability_F.data

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
    calculator = OptimalFlotation()
    price_per_ton_metal, charge_per_ton_conc, feed_flowrate, feed_grade = \
        0, 0, 0, 0
    recoveries, final_conc_grades, profits = [], [], []
    if calculator.validate_on_submit():
        price_per_ton_metal = calculator.price_per_ton_metal.data
        charge_per_ton_conc = calculator.charge_per_ton_conc.data
        feed_flowrate = calculator.feed_flowrate.data
        feed_grade = calculator.feed_grade.data
        recoveries_and_final_conc_grades = {}

        # Get the recovery and final concentrate grade values
        i = 1
        while True:
            recovery_name = f'recovery_{i}'
            final_conc_grade_name = f'final_conc_grade_{i}'
            form = request.form
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


if __name__ == '__main__':
    app.run(debug=True)  # Add debug=True to run the app in debug mode
